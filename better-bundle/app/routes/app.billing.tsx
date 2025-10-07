import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { Page } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { BillingStatusRouter } from "../components/Billing/BillingStatusRouter";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { getTrialRevenueData } from "../services/billing.service";

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    const billingPlan = await prisma.billing_plans.findFirst({
      where: { shop_domain: shop, status: "active" },
      include: { shops: true },
    });

    if (!billingPlan) {
      throw new Error("Billing plan not found");
    }

    let trialPlanAggregates: any = null;

    if (billingPlan.is_trial_active && billingPlan.type == "trial") {
      trialPlanAggregates = await getTrialRevenueData(billingPlan.shop_id);
    }

    const trialPlanData = {
      attributedRevenue: trialPlanAggregates.attributedRevenue,
      commissionEarned: trialPlanAggregates.commissionEarned,
      isTrialActive: billingPlan.is_trial_active,
      trialThreshold: billingPlan.trial_threshold,
    };

    return json({
      trialPlanData: trialPlanData,
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
  const { trialPlanData, shopCurrency } = useLoaderData<typeof loader>();
  console.log(trialPlanData, shopCurrency, "------------------>");

  return (
    <Page>
      <TitleBar title="Billing" />
      <div style={{ padding: "0 20px" }}>
        <div style={{ marginTop: "20px" }}>
          <BillingStatusRouter
            trialPlanData={trialPlanData}
            shopCurrency={shopCurrency}
          />
        </div>
      </div>
    </Page>
  );
}
