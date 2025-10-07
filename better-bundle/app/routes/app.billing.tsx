import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { Page, Tabs, BlockStack } from "@shopify/polaris";
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
    // Get shop info
    const shopInfo = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, currency_code: true },
    });

    const shopCurrency = shopInfo?.currency_code || "USD";

    // Get billing plan
    const billingPlan = await prisma.billing_plans.findFirst({
      where: { shop_domain: shop },
      orderBy: { created_at: "desc" },
    });

    if (!billingPlan) {
      return json({
        billingPlan: {
          is_trial_active: true,
          subscription_status: null,
          subscription_id: null,
          usage_count: 0,
          attributed_revenue: 0,
          trial_threshold: 200,
          currency: shopCurrency,
        },
        billing,
        recentInvoices: [],
      });
    }

    // ✅ Calculate current cycle metrics (if subscription active)
    let currentCycleMetrics = null;

    if (billingPlan.subscription_status === "ACTIVE" && shopInfo) {
      const now = new Date();

      // ✅ NEW: Use trial revenue utility to get accurate trial/post-trial separation
      const trialData = await getTrialRevenueData(shopInfo.id);

      // Calculate billing period from trial completion date
      const billingStartDate =
        trialData.trialPeriod.end || trialData.trialPeriod.start;
      const daysSinceTrialCompletion = Math.floor(
        (now.getTime() - billingStartDate.getTime()) / (1000 * 60 * 60 * 24),
      );

      // ✅ FIXED: Use trial completion date as period start, not calendar month
      // This ensures we only bill for POST-TRIAL revenue (industry standard)
      const period_start = billingStartDate;
      const period_end = now;

      // Use Prisma for simple queries, raw SQL only for complex cross-period logic
      const [purchasesAgg, refundsData] = await Promise.all([
        // Simple purchase aggregation with Prisma (type-safe)
        prisma.purchase_attributions.aggregate({
          where: {
            shop_id: shopInfo.id,
            purchase_at: {
              gte: period_start,
              lt: period_end,
            },
          },
          _count: true,
          _sum: { total_revenue: true },
        }),

        // ✅ FIXED: Only include POST-TRIAL refunds (industry standard)
        // This ensures trial period data is completely separated from billing
        prisma.$queryRaw<
          Array<{
            count: number;
            total: number;
            same_period_count: number;
            same_period_total: number;
            cross_period_count: number;
            cross_period_total: number;
          }>
        >`
          SELECT 
            COUNT(*)::int as count,
            COALESCE(SUM(ra.total_refunded_revenue), 0) as total,
            COUNT(*) FILTER (
              WHERE pa.purchase_at >= ${period_start} 
              AND pa.purchase_at < ${period_end}
            )::int as same_period_count,
            COALESCE(SUM(ra.total_refunded_revenue) FILTER (
              WHERE pa.purchase_at >= ${period_start} 
              AND pa.purchase_at < ${period_end}
            ), 0) as same_period_total,
            COUNT(*) FILTER (
              WHERE pa.purchase_at < ${period_start} 
              OR pa.purchase_at >= ${period_end}
              OR pa.purchase_at IS NULL
            )::int as cross_period_count,
            COALESCE(SUM(ra.total_refunded_revenue) FILTER (
              WHERE pa.purchase_at < ${period_start} 
              OR pa.purchase_at >= ${period_end}
              OR pa.purchase_at IS NULL
            ), 0) as cross_period_total
          FROM refund_attributions ra
          LEFT JOIN purchase_attributions pa ON ra.order_id = pa.order_id
          WHERE ra.shop_id = ${shopInfo.id}
          AND ra.refunded_at >= ${period_start}
          AND ra.refunded_at < ${period_end}
          -- ✅ CRITICAL: Only include refunds for purchases made AFTER trial completion
          -- This ensures trial period refunds are completely excluded from billing
          AND pa.purchase_at >= ${period_start}
        `,
      ]);

      const purchases = {
        count: purchasesAgg._count,
        total: Number(purchasesAgg._sum.total_revenue || 0),
      };

      const refunds = refundsData[0] || {
        count: 0,
        total: 0,
        same_period_count: 0,
        same_period_total: 0,
        cross_period_count: 0,
        cross_period_total: 0,
      };

      const purchasesTotal = Number(purchases.total || 0);
      // Only include refunds from purchases made in the current billing period
      const refundsTotal = Number(refunds.same_period_total || 0);
      const net_revenue = purchasesTotal - refundsTotal;
      const commission = net_revenue * 0.03;

      const capped_amount =
        (billingPlan.configuration as any)?.capped_amount || 1000;
      const final_commission = Math.min(commission, capped_amount);

      currentCycleMetrics = {
        purchases: { count: purchases.count || 0, total: purchasesTotal },
        refunds: {
          count: refunds.count || 0,
          total: refunds.total || 0,
          same_period_count: refunds.same_period_count || 0,
          same_period_total: Number(refunds.same_period_total || 0),
          cross_period_count: refunds.cross_period_count || 0,
          cross_period_total: Number(refunds.cross_period_total || 0),
        },
        net_revenue,
        commission,
        final_commission,
        capped_amount,
        days_remaining: Math.max(0, 30 - daysSinceTrialCompletion), // 30-day billing cycle from trial completion
        billing_period_start: period_start,
        billing_period_end: period_end,
        trial_completion_date: trialCompletedAt,
      };
    }

    // ✅ Fetch recent invoices
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
      />
    );
  };

  const formatCurrency = (
    amount: number | string,
    currency: string = "USD",
  ) => {
    const num = typeof amount === "string" ? parseFloat(amount) : amount;
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
    }).format(num);
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
        formatCurrency={formatCurrency}
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
