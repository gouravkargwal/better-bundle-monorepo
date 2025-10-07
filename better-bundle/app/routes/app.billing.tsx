import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { Page, Tabs } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { useState } from "react";
import { BillingStatusRouter } from "../components/Billing/BillingStatusRouter";
import { InvoicesHistory } from "../components/Billing/InvoiceHistory";
import { useBillingActions } from "../hooks/useBillingActions";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { getTrialRevenueData } from "../utils/trialRevenue";

export async function loader({ request }: LoaderFunctionArgs) {
  const { session, billing } = await authenticate.admin(request);
  const { shop } = session;

  try {
    const shopInfo = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: {
        id: true,
        currency_code: true,
        billing_plans: true,
      },
    });
    const shopCurrency = shopInfo?.currency_code;

    const billingPlan = shopInfo?.billing_plans || null;

    if (!billingPlan) {
      throw new Error("Billing plan not found");
    }

    let currentCycleMetrics = null;

    if (billingPlan.subscription_status === "ACTIVE" && shopInfo) {
      const now = new Date();
      const trialData = await getTrialRevenueData(shopInfo.id);

      // Calculate billing period from trial completion date
      const billingStartDate =
        trialData.trialPeriod.end || trialData.trialPeriod.start;
      const daysSinceTrialCompletion = Math.floor(
        (now.getTime() - billingStartDate.getTime()) / (1000 * 60 * 60 * 24),
      );

      const period_start = billingStartDate;
      const period_end = now;

      const purchasesAgg = await prisma.purchase_attributions.aggregate({
        where: {
          shop_id: shopInfo.id,
          purchase_at: {
            gte: period_start,
            lt: period_end,
          },
        },
        _count: true,
        _sum: { total_revenue: true },
      });

      const purchases = {
        count: purchasesAgg._count,
        total: Number(purchasesAgg._sum.total_revenue || 0),
      };

      const purchasesTotal = Number(purchases.total || 0);
      const commission = purchasesTotal * 0.03; // 3% of gross attributed revenue

      const capped_amount =
        (billingPlan.configuration as any)?.capped_amount || 1000;
      const final_commission = Math.min(commission, capped_amount);

      currentCycleMetrics = {
        purchases: { count: purchases.count || 0, total: purchasesTotal },
        attributed_revenue: purchasesTotal,
        commission,
        final_commission,
        capped_amount,
        days_remaining: Math.max(0, 30 - daysSinceTrialCompletion), // 30-day billing cycle from trial completion
        billing_period_start: period_start,
        billing_period_end: period_end,
        trial_completion_date: trialData.trialPeriod.end,
        refund_policy: "no_commission_refunds",
        policy_note:
          "Commission based on attributed revenue at time of purchase. Customer refunds do not affect commission as our recommendation service was successfully delivered.",
      };
    }

    const recentInvoices = shopInfo
      ? await prisma.billing_invoices.findMany({
          where: { shop_id: shopInfo.id },
          orderBy: { created_at: "desc" },
          take: 20,
          select: {
            id: true,
            invoice_number: true,
            status: true,
            total: true,
            subtotal: true,
            currency: true,
            period_start: true,
            period_end: true,
            due_date: true,
            paid_at: true,
            created_at: true,
            shopify_charge_id: true,
            billing_metadata: true,
          },
        })
      : [];

    return json({
      billingPlan: {
        ...billingPlan,
        currentCycleMetrics,
      },
      billing,
      recentInvoices,
      shopCurrency,
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
      billing: null,
      recentInvoices: [],
      error: "Failed to load billing data",
    });
  }
}

export default function BillingTabsPage() {
  const { billingPlan, billing, recentInvoices, shopCurrency } =
    useLoaderData<typeof loader>();
  const billingActions = useBillingActions(
    shopCurrency || (billingPlan as any).currency || "USD",
  );
  const [selectedTab, setSelectedTab] = useState(0);

  const tabs = [
    {
      id: "overview",
      content: "Overview",
      panelID: "overview-panel",
    },
    {
      id: "invoices",
      content: "Invoices",
      panelID: "invoices-panel",
    },
  ];

  const renderOverview = () => {
    return (
      <BillingStatusRouter
        billingPlan={billingPlan}
        billingActions={billingActions}
        billing={billing}
        shopCurrency={shopCurrency}
      />
    );
  };

  const formatDate = (date: string | Date) => {
    return new Date(date).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const getStatusBadge = (status: string) => {
    const statusLower = status.toLowerCase();

    if (statusLower === "paid") {
      return { tone: "success" as const, children: "Paid" };
    } else if (statusLower === "pending") {
      return { tone: "warning" as const, children: "Pending" };
    } else if (statusLower === "no_charge") {
      return { tone: "info" as const, children: "No Charge" };
    } else if (statusLower === "failed") {
      return { tone: "critical" as const, children: "Failed" };
    } else if (statusLower === "cancelled") {
      return { tone: "critical" as const, children: "Cancelled" };
    }

    return { tone: "info" as const, children: status };
  };

  const renderInvoices = () => {
    return (
      <InvoicesHistory
        billingData={{ recent_invoices: recentInvoices }}
        formatDate={formatDate}
        getStatusBadge={getStatusBadge}
      />
    );
  };

  const renderTabContent = () => {
    switch (selectedTab) {
      case 0:
        return renderOverview();
      case 1:
        return renderInvoices();
      default:
        return renderOverview();
    }
  };

  return (
    <Page>
      <TitleBar title="Billing" />
      <div style={{ padding: "0 20px" }}>
        <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
          <div style={{ marginTop: "20px" }}>{renderTabContent()}</div>
        </Tabs>
      </div>
    </Page>
  );
}
