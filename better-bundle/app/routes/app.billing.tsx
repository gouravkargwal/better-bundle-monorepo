import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { Page } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { BillingStatusRouter } from "../components/Billing/BillingStatusRouter";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { getBillingSummary } from "../services/billing.service";

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, currency_code: true },
    });

    if (!shopRecord) {
      throw new Error("Shop not found");
    }

    // Get comprehensive billing summary using new schema
    const billingSummary = await getBillingSummary(shopRecord.id);

    if (!billingSummary) {
      throw new Error("No billing data found");
    }

    // Format data for frontend compatibility
    const trialPlanData = billingSummary.trial
      ? {
          attributedRevenue: Number(billingSummary.trial.accumulated_revenue),
          commissionEarned:
            Number(billingSummary.trial.accumulated_revenue) * 0.03, // 3% commission
          isTrialActive: billingSummary.subscription.status === "TRIAL",
          trialThreshold: Number(billingSummary.trial.threshold),
        }
      : null;

    const currentCycleMetrics = billingSummary.current_cycle
      ? {
          purchases: { count: 0, total: 0 }, // Will be calculated from commission records
          net_revenue: Number(billingSummary.current_cycle.usage_amount),
          commission: Number(billingSummary.current_cycle.usage_amount) * 0.03,
          final_commission:
            Number(billingSummary.current_cycle.usage_amount) * 0.03,
          capped_amount: Number(billingSummary.current_cycle.current_cap),
          days_remaining: billingSummary.current_cycle.days_remaining || 0,
        }
      : null;

    // Create billing plan object for frontend compatibility
    const billingPlan = {
      id: billingSummary.subscription.id,
      status: billingSummary.subscription.status.toLowerCase(),
      type:
        billingSummary.subscription.status === "TRIAL"
          ? "trial"
          : "usage_based",
      is_trial_active: billingSummary.subscription.status === "TRIAL",
      trial_threshold: billingSummary.trial?.threshold || 0,
      subscription_status:
        billingSummary.shopify_subscription?.status || "PENDING",
      configuration: {
        currency: billingSummary.pricing_tier.currency,
        revenue_share_rate: Number(billingSummary.pricing_tier.commission_rate),
      },
      currentCycleMetrics,
    };

    return json({
      trialPlanData: trialPlanData,
      billingPlan: billingPlan,
      shopCurrency: shopRecord.currency_code,
    });
  } catch (error) {
    console.log(error, "------------------>");

    return json({
      error: "Failed to load billing data",
    });
  }
}

export default function BillingTabsPage() {
  const loaderData = useLoaderData<typeof loader>();
  const { trialPlanData, billingPlan, shopCurrency } = loaderData as any;
  console.log(trialPlanData, billingPlan, shopCurrency, "------------------>");

  return (
    <Page>
      <TitleBar title="Billing" />
      <div style={{ padding: "0 20px" }}>
        <div style={{ marginTop: "20px" }}>
          <BillingStatusRouter
            trialPlanData={trialPlanData}
            billingPlan={billingPlan}
            shopCurrency={shopCurrency}
          />
        </div>
      </div>
    </Page>
  );
}
