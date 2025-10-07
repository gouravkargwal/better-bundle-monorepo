import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData, useFetcher } from "@remix-run/react";
import { Page, Tabs, Spinner, Banner, Button } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { useState, useEffect, useRef } from "react";
import { BillingStatusRouter } from "../components/Billing/BillingStatusRouter";
import { InvoicesHistory } from "../components/Billing/InvoiceHistory";
import { useBillingActions } from "../hooks/useBillingActions";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { getTrialRevenueData } from "../utils/trialRevenue";

// Helper to compute trial revenue with cycle filtering and fallback
async function computeTrialRevenue(shopId: string, trialData: any) {
  const periodStart = trialData.trialPeriod.start;
  const periodEnd = trialData.trialPeriod.end || new Date();

  try {
    const trialAgg = await prisma.commission_records.aggregate({
      where: {
        shop_id: shopId,
        billing_phase: "TRIAL",
        created_at: { gte: periodStart, lt: periodEnd },
      },
      _sum: { attributed_revenue: true, commission_earned: true },
    });
    return {
      revenue: Number(trialAgg._sum.attributed_revenue || 0),
      commission: Number(trialAgg._sum.commission_earned || 0),
    };
  } catch {
    const purchasesAgg = await prisma.purchase_attributions.aggregate({
      where: {
        shop_id: shopId,
        purchase_at: { gte: periodStart, lt: periodEnd },
      },
      _sum: { total_revenue: true },
    });
    const revenue = Number(purchasesAgg._sum.total_revenue || 0);
    return { revenue, commission: revenue * 0.03 };
  }
}

// Helper to compute current cycle metrics
async function computeCurrentCycleMetrics(
  shopId: string,
  billingPlan: any,
  trialData: any,
) {
  const now = new Date();
  const billingStartDate =
    trialData.trialPeriod.end || trialData.trialPeriod.start;
  const daysSinceTrialCompletion = Math.floor(
    (now.getTime() - billingStartDate.getTime()) / (1000 * 60 * 60 * 24),
  );

  const periodStart = billingStartDate;
  const periodEnd = now;

  try {
    const cycleAgg = await prisma.commission_records.aggregate({
      where: {
        shop_id: shopId,
        billing_phase: "ACTIVE",
        created_at: { gte: periodStart, lt: periodEnd },
      },
      _count: true,
      _sum: { attributed_revenue: true, commission_earned: true },
    });

    const attributedRevenue = Number(cycleAgg._sum.attributed_revenue || 0);
    const commission = Number(cycleAgg._sum.commission_earned || 0);
    const cappedAmount =
      (billingPlan.configuration as any)?.capped_amount || 1000;
    const finalCommission = Math.min(commission, cappedAmount);

    return {
      purchases: { count: cycleAgg._count || 0, total: attributedRevenue },
      attributed_revenue: attributedRevenue,
      commission,
      final_commission: finalCommission,
      capped_amount: cappedAmount,
      days_remaining: Math.max(0, 30 - daysSinceTrialCompletion),
      billing_period_start: periodStart,
      billing_period_end: periodEnd,
      trial_completion_date: trialData.trialPeriod.end,
      refund_policy: "no_commission_refunds",
      policy_note:
        "Commission based on attributed revenue at time of purchase. Customer refunds do not affect commission as our recommendation service was successfully delivered.",
    };
  } catch {
    const purchasesAgg = await prisma.purchase_attributions.aggregate({
      where: {
        shop_id: shopId,
        purchase_at: { gte: periodStart, lt: periodEnd },
      },
      _count: true,
      _sum: { total_revenue: true },
    });

    const purchasesTotal = Number(purchasesAgg._sum.total_revenue || 0);
    const commission = purchasesTotal * 0.03;
    const cappedAmount =
      (billingPlan.configuration as any)?.capped_amount || 1000;
    const finalCommission = Math.min(commission, cappedAmount);

    return {
      purchases: { count: purchasesAgg._count || 0, total: purchasesTotal },
      attributed_revenue: purchasesTotal,
      commission,
      final_commission: finalCommission,
      capped_amount: cappedAmount,
      days_remaining: Math.max(0, 30 - daysSinceTrialCompletion),
      billing_period_start: periodStart,
      billing_period_end: periodEnd,
      trial_completion_date: trialData.trialPeriod.end,
      refund_policy: "no_commission_refunds",
      policy_note:
        "Commission based on attributed revenue at time of purchase. Customer refunds do not affect commission as our recommendation service was successfully delivered.",
    };
  }
}

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    const shopInfo = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, currency_code: true, billing_plans: true },
    });

    if (!shopInfo?.id) {
      throw new Error("Shop info not found");
    }

    const billingPlan = shopInfo.billing_plans;
    if (!billingPlan) {
      throw new Error("Billing plan not found");
    }

    let trialData = null;
    let trialRevenueData = { revenue: 0, commission: 0 };
    let currentCycleMetrics = null;

    if (
      billingPlan.is_trial_active ||
      billingPlan.subscription_status === "ACTIVE"
    ) {
      trialData = await getTrialRevenueData(shopInfo.id);
      trialRevenueData = await computeTrialRevenue(shopInfo.id, trialData);
    }

    if (billingPlan.subscription_status === "ACTIVE") {
      currentCycleMetrics = await computeCurrentCycleMetrics(
        shopInfo.id,
        billingPlan,
        trialData,
      );
    }

    return json({
      billingPlan: {
        ...billingPlan,
        trial_revenue: trialRevenueData.revenue,
        trial_commission: trialRevenueData.commission,
        currentCycleMetrics,
      },
      shopCurrency: shopInfo.currency_code || "USD",
    });
  } catch (error) {
    console.error("Error loading billing data:", error);
    return json({
      billingPlan: {
        is_trial_active: true,
        subscription_status: null,
        subscription_id: null,
        usage_count: 0,
        attributed_revenue: 0,
        trial_threshold: 200,
        currency: "USD",
      },
      shopCurrency: "USD",
      error: "Failed to load billing data",
    });
  }
}

export default function BillingTabsPage() {
  const { billingPlan, shopCurrency } = useLoaderData<typeof loader>();
  const billingActions = useBillingActions(
    shopCurrency || billingPlan?.currency || "USD",
  );
  const [selectedTab, setSelectedTab] = useState(0);
  const fetcher = useFetcher<{ recentInvoices?: any[]; error?: string }>();
  const [invoicesData, setInvoicesData] = useState<any[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoadingInvoices, setIsLoadingInvoices] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const tabs = [
    { id: "overview", content: "Overview", panelID: "overview-panel" },
    { id: "invoices", content: "Invoices", panelID: "invoices-panel" },
  ];

  // Handle tab selection
  const handleTabSelect = (newTab: number) => {
    try {
      setSelectedTab(newTab);
      console.log("Tab selected:", newTab);

      // Load invoices when invoices tab is selected
      if (newTab === 1 && !invoicesData && !isLoadingInvoices) {
        console.log("Triggering fetch for invoices tab");
        setLoadError(null);
        setIsLoadingInvoices(true);

        // IMPORTANT: Use the correct route path
        fetcher.load("/app/billing/invoices?index");

        // Set timeout for loading
        timeoutRef.current = setTimeout(() => {
          setLoadError("Loading timed out. Please retry.");
          setIsLoadingInvoices(false);
        }, 10000);
      }
    } catch (error) {
      console.error("Error selecting tab:", error);
      setIsLoadingInvoices(false);
    }
  };

  // Handle retry
  const handleRetry = () => {
    setLoadError(null);
    setIsLoadingInvoices(true);
    fetcher.load("/app/billing/invoices");

    timeoutRef.current = setTimeout(() => {
      setLoadError("Loading timed out. Please retry.");
      setIsLoadingInvoices(false);
    }, 10000);
  };

  // Monitor fetcher state changes
  useEffect(() => {
    console.log("Fetcher state:", fetcher.state);
    console.log("Fetcher data:", fetcher.data);

    if (fetcher.state === "idle" && isLoadingInvoices) {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      setIsLoadingInvoices(false);

      if (fetcher.data?.recentInvoices) {
        console.log(
          "Invoices loaded successfully:",
          fetcher.data.recentInvoices,
        );
        setInvoicesData(fetcher.data.recentInvoices);
        setLoadError(null);
      } else if (fetcher.data?.error) {
        console.error("Error loading invoices:", fetcher.data.error);
        setLoadError(fetcher.data.error);
      }
    }
  }, [fetcher.state, fetcher.data, isLoadingInvoices]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  // Render invoices tab content
  const renderInvoicesTab = () => {
    // Show loading state
    if (isLoadingInvoices || fetcher.state === "loading") {
      return (
        <div
          style={{ display: "flex", justifyContent: "center", padding: "40px" }}
        >
          <Spinner accessibilityLabel="Loading invoices" size="large" />
        </div>
      );
    }

    // Show error state
    if (loadError || fetcher.data?.error) {
      return (
        <Banner title="Error loading invoices" tone="critical">
          <p>{loadError || fetcher.data?.error || "Unknown error occurred."}</p>
          <Button onClick={handleRetry}>Retry</Button>
        </Banner>
      );
    }

    // Show empty state if no data loaded yet
    if (!invoicesData) {
      return (
        <Banner title="No invoices data" tone="info">
          <p>Click retry to load invoices.</p>
          <Button onClick={handleRetry}>Load Invoices</Button>
        </Banner>
      );
    }

    // Show invoices data
    return <InvoicesHistory billingData={{ recent_invoices: invoicesData }} />;
  };

  return (
    <Page>
      <TitleBar title="Billing" />
      <div style={{ padding: "0 20px" }}>
        <Tabs tabs={tabs} selected={selectedTab} onSelect={handleTabSelect}>
          <div style={{ marginTop: "20px" }}>
            {selectedTab === 0 ? (
              <BillingStatusRouter
                billingPlan={billingPlan}
                billingActions={billingActions}
                shopCurrency={shopCurrency}
              />
            ) : (
              renderInvoicesTab()
            )}
          </div>
        </Tabs>
      </div>
    </Page>
  );
}
