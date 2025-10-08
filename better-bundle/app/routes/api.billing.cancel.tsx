import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function action({ request }: ActionFunctionArgs) {
  const { session, billing } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true },
    });

    if (!shopRecord) {
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    // Get shop subscription
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        is_active: true,
      },
      include: {
        shopify_subscription: true,
      },
    });

    if (!shopSubscription) {
      return json(
        { success: false, error: "No active subscription found" },
        { status: 404 },
      );
    }

    const subscriptionId =
      shopSubscription.shopify_subscription?.shopify_subscription_id;

    // HANDLE PENDING SUBSCRIPTIONS: clear local state and guide merchant to Shopify billing
    if (shopSubscription.status === "pending_approval") {
      await prisma.shop_subscriptions.update({
        where: { id: shopSubscription.id },
        data: {
          status: "cancelled",
          cancelled_at: new Date(),
          updated_at: new Date(),
        },
      });

      return json({
        success: true,
        message:
          "Pending subscription cleared. You can now create a new subscription.",
        wasPending: true,
      });
    }

    // HANDLE ACTIVE SUBSCRIPTIONS
    if (!subscriptionId) {
      return json(
        { success: false, error: "No active subscription found" },
        { status: 404 },
      );
    }

    // Ensure the id is a GID. If a raw id was stored, coerce to GID.
    const idIsGid =
      typeof subscriptionId === "string" && subscriptionId.startsWith("gid://");
    const gid = idIsGid
      ? subscriptionId
      : `gid://shopify/AppSubscription/${subscriptionId}`;

    // Use Shopify's billing client as requested
    await billing.cancel({ subscriptionId: gid });

    // Update shop subscription
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        status: "cancelled",
        cancelled_at: new Date(),
        updated_at: new Date(),
      },
    });

    // Update Shopify subscription record
    if (shopSubscription.shopify_subscription) {
      await prisma.shopify_subscriptions.update({
        where: { id: shopSubscription.shopify_subscription.id },
        data: {
          status: "cancelled",
          cancelled_at: new Date(),
          updated_at: new Date(),
        },
      });
    }

    console.log(`✅ Successfully cancelled subscription for shop ${shop}`);

    return json({
      success: true,
      message: "Subscription cancelled successfully",
    });
  } catch (error) {
    console.error("❌ Error cancelling subscription:", error);
    return json(
      {
        success: false,
        error: "Failed to cancel subscription",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
