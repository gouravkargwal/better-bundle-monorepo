import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    console.log(`🔍 Getting billing status for shop ${shop}`);

    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, currency_code: true, is_active: true },
    });

    if (!shopRecord) {
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    // Get billing plan
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shopRecord.id,
        status: { in: ["active", "suspended"] },
      },
    });

    if (!billingPlan) {
      return json({
        shop_id: shopRecord.id,
        billing_status: "no_plan",
        message: "No billing plan found",
      });
    }

    // Determine billing status
    let status: string;
    let message: string;

    if (billingPlan.is_trial_active) {
      // ✅ NO REFUND COMMISSION POLICY - Only calculate gross attributed revenue
      const purchasesAgg = await prisma.purchase_attributions.aggregate({
        where: { shop_id: shopRecord.id },
        _sum: { total_revenue: true },
      });

      const currentRevenue = Number(purchasesAgg._sum.total_revenue || 0);
      const threshold = billingPlan.trial_threshold || 200;

      status = "trial_active";
      message = `Trial active - $${currentRevenue} / $${threshold} revenue`;
    } else if (billingPlan.subscription_status === "active") {
      status = "subscription_active";
      message = "Subscription active";
    } else if (billingPlan.subscription_status === "pending") {
      status = "subscription_pending";
      message = "Subscription pending approval";
    } else if (billingPlan.subscription_status === "declined") {
      status = "subscription_declined";
      message = "Subscription declined";
    } else {
      status = "suspended";
      message = "Services suspended";
    }

    return json({
      shop_id: shopRecord.id,
      billing_status: status,
      message,
      trial_active: billingPlan.is_trial_active,
      trial_revenue: billingPlan.trial_revenue || 0,
      trial_threshold: billingPlan.trial_threshold || 200,
      subscription_id: billingPlan.subscription_id,
      subscription_status: billingPlan.subscription_status,
      subscription_confirmation_url: billingPlan.subscription_confirmation_url,
      requires_subscription_approval:
        billingPlan.requires_subscription_approval,
      shop_active: shopRecord.is_active,
    });
  } catch (error) {
    console.error("❌ Error getting billing status:", error);
    return json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
