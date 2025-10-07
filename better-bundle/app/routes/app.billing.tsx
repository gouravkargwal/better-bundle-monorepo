import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { Page } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { BillingStatusRouter } from "../components/Billing/BillingStatusRouter";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import {
  getTrialRevenueData,
  getCurrentCycleMetrics,
} from "../services/billing.service";

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Get the latest billing plan (could be trial, pending, or active)
    const billingPlan = await prisma.billing_plans.findFirst({
      where: { shop_domain: shop },
      include: { shops: true },
      orderBy: { created_at: "desc" },
    });

    if (!billingPlan) {
      throw new Error("Billing plan not found");
    }

    let trialPlanAggregates: any = null;
    let currentCycleMetrics: any = null;

    if (billingPlan.is_trial_active && billingPlan.type == "trial") {
      trialPlanAggregates = await getTrialRevenueData(billingPlan.shop_id);
    } else if (
      billingPlan.status === "active" &&
      billingPlan.subscription_status === "ACTIVE"
    ) {
      // Get current cycle metrics for active subscription
      currentCycleMetrics = await getCurrentCycleMetrics(
        billingPlan.shop_id,
        billingPlan,
      );
    }

    const trialPlanData = trialPlanAggregates
      ? {
          attributedRevenue: trialPlanAggregates.attributedRevenue,
          commissionEarned: trialPlanAggregates.commissionEarned,
          isTrialActive: billingPlan.is_trial_active,
          trialThreshold: billingPlan.trial_threshold,
        }
      : null;

    // Add current cycle metrics to billing plan
    const billingPlanWithMetrics = {
      ...billingPlan,
      currentCycleMetrics,
    };

    return json({
      trialPlanData: trialPlanData,
      billingPlan: billingPlanWithMetrics,
      shopCurrency: billingPlan.shops?.currency_code,
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
