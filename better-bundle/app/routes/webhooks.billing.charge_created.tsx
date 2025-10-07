import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function action({ request }: ActionFunctionArgs) {
  const { topic, shop, payload } = await authenticate.webhook(request);

  console.log(`🔔 Subscription webhook received: ${topic} for shop ${shop}`);

  try {
    // Parse the webhook payload (Admin REST: app_subscription has admin_graphql_api_id)
    const raw = (payload as any) || {};
    const appSub = raw.app_subscription || raw.data?.app_subscription || raw;
    const subscriptionId: string | undefined =
      appSub?.admin_graphql_api_id || appSub?.id;
    const subscriptionStatus: string | undefined = appSub?.status;

    // Check for cap increase (APP_SUBSCRIPTIONS_UPDATE webhook)
    const lineItems = appSub?.line_items || [];
    const currentCappedAmount =
      lineItems[0]?.plan?.pricing_details?.capped_amount?.amount;

    if (!subscriptionId || !subscriptionStatus) {
      console.error("❌ No subscription data in webhook payload");
      return json(
        { success: false, error: "No subscription data" },
        { status: 400 },
      );
    }

    console.log("📋 Subscription updated:", {
      id: subscriptionId,
      status: subscriptionStatus,
      shop: shop,
      currentCappedAmount: currentCappedAmount,
    });

    // Find shop record and the latest active/suspended billing plan for this shop
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, shop_domain: true },
    });

    if (!shopRecord) {
      console.log(`⚠️ No shop record found for domain ${shop}`);
      return json({ success: true });
    }

    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shopRecord.id,
        status: { in: ["active", "suspended", "pending"] },
      },
      orderBy: { created_at: "desc" },
    });

    if (billingPlan) {
      const currentId =
        (billingPlan as any).subscription_id ||
        (billingPlan.configuration as any)?.subscription_id;

      const isDifferentFromCurrent = currentId && currentId !== subscriptionId;
      const isNegativeStatus = ["CANCELLED", "DECLINED", "EXPIRED"].includes(
        (subscriptionStatus || "").toUpperCase(),
      );

      // Ignore negative status for a non-current (older) subscription id
      if (isDifferentFromCurrent && isNegativeStatus) {
        console.log(
          `ℹ️ Ignoring ${subscriptionStatus} for non-current subscription ${subscriptionId}; current is ${currentId}`,
        );
        return json({ success: true });
      }

      // Allow ACTIVE to promote a new subscription id; otherwise require match
      // Also allow updates for pending subscriptions (new billing plan flow)
      const canUpdate =
        subscriptionStatus === "ACTIVE" ||
        !isDifferentFromCurrent ||
        billingPlan.status === "pending";

      if (!canUpdate) {
        console.log(
          `ℹ️ Skipping update: incoming ${subscriptionId} doesn't match current ${currentId}`,
        );
        return json({ success: true });
      }

      // Check for cap increase
      const previousCap = Number(
        (billingPlan.configuration as any)?.capped_amount || 1000,
      );
      const newCap = Number(currentCappedAmount || previousCap);
      const isCapIncrease = newCap > previousCap;

      // Update billing plan with subscription status
      await prisma.billing_plans.update({
        where: { id: billingPlan.id },
        data: {
          subscription_id: subscriptionId,
          subscription_status: subscriptionStatus,
          subscription_activated_at:
            subscriptionStatus === "ACTIVE" ? new Date() : null,
          configuration: {
            ...(billingPlan.configuration as any),
            subscription_id: subscriptionId,
            subscription_status: subscriptionStatus,
            subscription_updated_at: new Date().toISOString(),
            subscription_activated_at:
              subscriptionStatus === "ACTIVE" ? new Date().toISOString() : null,
            // Update capped amount if it increased
            ...(isCapIncrease && {
              capped_amount: newCap,
              cap_increased_at: new Date().toISOString(),
              previous_cap: previousCap,
            }),
          },
        },
      });

      // Also mark shop active when subscription becomes ACTIVE
      if (subscriptionStatus === "ACTIVE") {
        // Update billing plan status to active
        await prisma.billing_plans.updateMany({
          where: { id: billingPlan.id },
          data: {
            status: "active",
            subscription_status: "ACTIVE",
            requires_subscription_approval: false,
            subscription_activated_at: new Date(),
            configuration: {
              ...(billingPlan.configuration as any),
              subscription_status: "ACTIVE",
              subscription_activated_at: new Date().toISOString(),
              services_suspended: false,
            },
          },
        });

        // Reactivate shop services
        await prisma.shops.updateMany({
          where: { id: shopRecord.id },
          data: {
            is_active: true,
            suspended_at: null as any,
            suspension_reason: null as any,
            service_impact: null as any,
            updated_at: new Date(),
          },
        });

        console.log(
          `🎉 Subscription activated! Shop ${shop} services resumed.`,
        );
      }

      // Handle cap increase - reactivate services if suspended due to cap
      if (isCapIncrease && subscriptionStatus === "ACTIVE") {
        console.log(
          `📈 Cap increased detected: ${previousCap} → ${newCap} for shop ${shop}`,
        );

        // Check if shop was suspended due to cap reached
        const currentShopRecord = await prisma.shops.findUnique({
          where: { id: shopRecord.id },
          select: { suspension_reason: true, is_active: true },
        });

        if (
          currentShopRecord?.suspension_reason === "monthly_cap_reached" &&
          !currentShopRecord.is_active
        ) {
          // Reactivate shop services
          await prisma.shops.update({
            where: { id: shopRecord.id },
            data: {
              is_active: true,
              suspended_at: null,
              suspension_reason: null,
              service_impact: null,
              updated_at: new Date(),
            },
          });

          console.log(
            `🚀 Shop ${shop} services reactivated after cap increase!`,
          );
        }
      }

      console.log(
        `✅ Updated billing plan ${billingPlan.id} with subscription ${subscriptionId}`,
      );
    } else {
      console.log(
        `⚠️ No billing plan found for shop ${shopRecord.shop_domain} (id=${shopRecord.id})`,
      );
    }

    console.log(`✅ Billing webhook processed successfully for shop ${shop}`);

    return json({ success: true });
  } catch (error) {
    console.error("❌ Error processing billing webhook:", error);
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}
