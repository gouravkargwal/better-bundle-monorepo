import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function action({ request }: ActionFunctionArgs) {
  const { session, billing } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Get the current billing plan
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shops: {
          shop_domain: shop,
        },
      },
      orderBy: { created_at: "desc" },
    });

    if (!billingPlan) {
      return json(
        { success: false, error: "No billing plan found" },
        { status: 404 },
      );
    }

    // Determine subscription id from either top-level columns or configuration blob
    const configuration = (billingPlan.configuration as any) || {};
    const subscriptionId: string | null =
      (billingPlan as any).subscription_id ||
      configuration.subscription_id ||
      null;

    // HANDLE PENDING SUBSCRIPTIONS: clear local state and guide merchant to Shopify billing
    if (
      billingPlan.subscription_status === "PENDING" ||
      configuration.subscription_status === "PENDING"
    ) {
      await prisma.billing_plans.update({
        where: { id: billingPlan.id },
        data: {
          subscription_id: null,
          subscription_line_item_id: null,
          subscription_status: null,
          subscription_confirmation_url: null,
          subscription_created_at: null,
          configuration: {
            ...configuration,
            subscription_id: null,
            subscription_status: null,
            subscription_created_at: null,
          },
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

    // Update billing plan
    const configurationAfter = (billingPlan.configuration as any) || {};
    const now = new Date();

    await prisma.billing_plans.update({
      where: { id: billingPlan.id },
      data: {
        subscription_status: "CANCELLED",
        configuration: {
          ...configurationAfter,
          subscription_status: "CANCELLED",
          subscription_cancelled_at: now.toISOString(),
          cancellation_reason: "Cancelled by merchant",
        },
      },
    });

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
