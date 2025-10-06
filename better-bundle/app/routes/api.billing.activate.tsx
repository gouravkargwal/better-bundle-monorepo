import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function action({ request }: ActionFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    const formData = await request.formData();
    const subscriptionId = formData.get("subscription_id") as string;

    if (!subscriptionId) {
      return json(
        { success: false, error: "Subscription ID is required" },
        { status: 400 },
      );
    }

    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true },
    });

    if (!shopRecord) {
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    // Get billing plan with the subscription
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shopRecord.id,
        subscription_id: subscriptionId,
      },
    });

    if (!billingPlan) {
      return json(
        { success: false, error: "Billing plan not found for subscription" },
        { status: 404 },
      );
    }

    // Update billing plan status
    await prisma.billing_plans.updateMany({
      where: { id: billingPlan.id },
      data: {
        subscription_status: "ACTIVE",
        status: "active",
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
      where: { shop_domain: shop },
      data: {
        is_active: true,
        suspended_at: null,
        suspension_reason: null,
        service_impact: null,
        updated_at: new Date(),
      },
    });

    return json({
      success: true,
      message: "Subscription activated successfully",
      subscription_id: subscriptionId,
    });
  } catch (error) {
    console.error("❌ Error activating subscription:", error);
    return json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
