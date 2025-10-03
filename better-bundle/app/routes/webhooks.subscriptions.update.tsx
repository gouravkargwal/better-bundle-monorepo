/**
 * Shopify Webhook: APP_SUBSCRIPTIONS_UPDATE
 *
 * This webhook is triggered when:
 * - Subscription is approved by merchant
 * - Subscription status changes
 * - Merchant changes capped amount
 */

import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function action({ request }: ActionFunctionArgs) {
  const { topic, shop, payload } = await authenticate.webhook(request);

  console.log(`🔔 Subscription webhook received: ${topic} for shop ${shop}`);

  try {
    const subscriptionData = payload.app_subscription;

    if (!subscriptionData) {
      console.error("❌ No subscription data in webhook payload");
      return json(
        { success: false, error: "No subscription data" },
        { status: 400 },
      );
    }

    console.log("📋 Subscription data:", {
      id: subscriptionData.id,
      name: subscriptionData.name,
      status: subscriptionData.status,
      shop: shop,
    });

    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true },
    });

    if (!shopRecord) {
      console.error(`❌ Shop not found: ${shop}`);
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    // Get billing plan
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shopRecord.id,
        subscription_id: subscriptionData.id.split("/").pop(), // Extract ID from gid://
      },
    });

    if (!billingPlan) {
      console.error(
        `❌ Billing plan not found for subscription ${subscriptionData.id}`,
      );
      return json(
        { success: false, error: "Billing plan not found" },
        { status: 404 },
      );
    }

    const newStatus = subscriptionData.status;
    const oldStatus = billingPlan.subscription_status;

    console.log(`📊 Status change: ${oldStatus} → ${newStatus}`);

    // Update billing plan with new status
    await prisma.billing_plans.update({
      where: { id: billingPlan.id },
      data: {
        subscription_status: newStatus,
        status: newStatus === "ACTIVE" ? "active" : billingPlan.status,
        requires_subscription_approval: newStatus !== "ACTIVE",
        configuration: {
          ...(billingPlan.configuration as any),
          subscription_status: newStatus,
          subscription_updated_at: new Date().toISOString(),
        },
      },
    });

    // Handle status-specific actions
    if (newStatus === "ACTIVE" && oldStatus !== "ACTIVE") {
      // ✅ SUBSCRIPTION ACTIVATED - Resume services
      console.log(`✅ Subscription activated for shop ${shop}`);

      // Reactivate shop
      await prisma.shops.update({
        where: { shop_domain: shop },
        data: {
          is_active: true,
          suspended_at: null,
          suspension_reason: null,
          service_impact: null,
          updated_at: new Date(),
        },
      });

      // Create activation event
      await prisma.billing_events.create({
        data: {
          shop_id: shopRecord.id,
          type: "subscription_activated",
          data: {
            subscription_id: subscriptionData.id,
            status: "ACTIVE",
            activated_at: new Date().toISOString(),
            services_resumed: true,
          },
          billing_metadata: {
            webhook_topic: topic,
            phase: "subscription_activation",
          },
          occurred_at: new Date(),
        },
      });

      console.log(`🎉 Services resumed for shop ${shop}`);
    } else if (newStatus === "DECLINED") {
      // ❌ SUBSCRIPTION DECLINED - Keep services suspended
      console.log(`❌ Subscription declined for shop ${shop}`);

      await prisma.billing_events.create({
        data: {
          shop_id: shopRecord.id,
          type: "subscription_declined",
          data: {
            subscription_id: subscriptionData.id,
            status: "DECLINED",
            declined_at: new Date().toISOString(),
          },
          billing_metadata: {
            webhook_topic: topic,
          },
          occurred_at: new Date(),
        },
      });
    } else if (newStatus === "CANCELLED") {
      // 🛑 SUBSCRIPTION CANCELLED - Suspend services
      console.log(`🛑 Subscription cancelled for shop ${shop}`);

      await prisma.shops.update({
        where: { shop_domain: shop },
        data: {
          is_active: false,
          suspended_at: new Date(),
          suspension_reason: "subscription_cancelled",
          service_impact: "suspended",
        },
      });

      await prisma.billing_events.create({
        data: {
          shop_id: shopRecord.id,
          type: "subscription_cancelled",
          data: {
            subscription_id: subscriptionData.id,
            status: "CANCELLED",
            cancelled_at: new Date().toISOString(),
            services_suspended: true,
          },
          billing_metadata: {
            webhook_topic: topic,
          },
          occurred_at: new Date(),
        },
      });
    }

    // Update general subscription status event
    await prisma.billing_events.create({
      data: {
        shop_id: shopRecord.id,
        type: "subscription_updated",
        data: {
          subscription_id: subscriptionData.id,
          old_status: oldStatus,
          new_status: newStatus,
          updated_at: new Date().toISOString(),
        },
        billing_metadata: {
          webhook_topic: topic,
        },
        occurred_at: new Date(),
      },
    });

    console.log(`✅ Webhook processed successfully for shop ${shop}`);

    return json({ success: true });
  } catch (error) {
    console.error("❌ Error processing subscription webhook:", error);
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}
