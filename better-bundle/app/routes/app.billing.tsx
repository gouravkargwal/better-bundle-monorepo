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

export async function loader({ request }: LoaderFunctionArgs) {
  const { session, billing } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Get shop info for currency
    const shopInfo = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { currency_code: true },
    });

    const shopCurrency = shopInfo?.currency_code || "USD";

    // Get billing plan for the shop
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_domain: shop, // Use shop_domain instead of shop_id
        // Remove status filter to get any billing plan
      },
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
          trial_threshold: 200, // Default trial threshold
          currency: shopCurrency,
        },
      });
    }

    // Compute idempotent trial progress from attribution tables
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true },
    });
    const shopId = shopRecord?.id || billingPlan.shop_id;

    const purchasesAgg = await prisma.purchase_attributions.aggregate({
      where: { shop_id: shopId },
      _sum: { total_revenue: true },
    });
    const refundsAgg = await prisma.refund_attributions.aggregate({
      where: { shop_id: shopId },
      _sum: { total_refunded_revenue: true },
    });
    const ordersTracked = await prisma.purchase_attributions.count({
      where: { shop_id: shopId },
    });

    const purchases = Number(purchasesAgg._sum.total_revenue || 0);
    const refunds = Number(refundsAgg._sum.total_refunded_revenue || 0);
    const netAttributed = Math.max(0, purchases - refunds);

    // Map the billing plan data to the correct field names for the UI
    const updatedBillingPlan = {
      ...billingPlan,
      attributed_revenue: netAttributed,
      usage_count: ordersTracked,
      currency: shopCurrency,
    };

    return json({ billingPlan: updatedBillingPlan, billing: billing });
  } catch (error) {
    console.error("Error loading billing data:", error);

    // Try to get shop currency even in error case
    let shopCurrency = "UNKNOWN";
    try {
      const shopInfo = await prisma.shops.findUnique({
        where: { shop_domain: shop },
        select: { currency_code: true },
      });
      shopCurrency = shopInfo?.currency_code || "UNKNOWN";
    } catch (e) {
      // Use UNKNOWN as fallback
    }

    return json({
      billingPlan: {
        is_trial_active: true,
        subscription_status: null,
        subscription_id: null,
        usage_count: 0,
        attributed_revenue: 0,
        trial_threshold: 0, // No default trial threshold
        currency: shopCurrency,
      },
    });
  }
}

export default function BillingTabsPage() {
  const { billingPlan, billing } = useLoaderData<typeof loader>();
  const billingActions = useBillingActions(billingPlan.currency);
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
    console.log("🔍 Render Overview - Billing Plan:", billingPlan);
    return (
      <BillingStatusRouter
        billingPlan={billingPlan}
        billingActions={billingActions}
        billing={billing}
      />
    );
  };

  const renderInvoices = () => {
    // Create billing data structure for the component
    const billingData = {
      recent_invoices: [], // We'll need to fetch this from database
    };

    const formatDate = (date: string) => new Date(date).toLocaleDateString();
    const getStatusBadge = (status: string) => {
      const tone =
        status === "paid"
          ? "success"
          : status === "pending"
            ? "warning"
            : "critical";
      return { tone, children: status.toUpperCase() };
    };

    return (
      <InvoicesHistory
        billingData={billingData}
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
          {renderTabContent()}
        </Tabs>
      </div>
    </Page>
  );
}
