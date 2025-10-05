import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { Page, Tabs } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { useState } from "react";
import { BillingStatusRouter } from "../components/Billing/BillingStatusRouter";
import { BillingEvents } from "../components/Billing/BillingEvents";
import { InvoicesHistory } from "../components/Billing/InvoiceHistory";
import { useBillingActions } from "../hooks/useBillingActions";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
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

    console.log("🔍 Database Query Result:", {
      shop,
      billingPlan: billingPlan
        ? {
            id: billingPlan.id,
            shop_id: billingPlan.shop_id,
            trial_threshold: billingPlan.trial_threshold,
            trial_revenue: billingPlan.trial_revenue,
            trial_usage_records_count: billingPlan.trial_usage_records_count,
            subscription_status: billingPlan.subscription_status,
            is_trial_active: billingPlan.is_trial_active,
          }
        : null,
    });

    // Check if there are any billing plans for this shop with any status
    const allBillingPlans = await prisma.billing_plans.findMany({
      where: {
        shop_domain: shop, // Use shop_domain instead of shop_id
      },
      orderBy: { created_at: "desc" },
    });

    console.log("🔍 All Billing Plans for Shop:", {
      shop,
      count: allBillingPlans.length,
      plans: allBillingPlans.map((plan) => ({
        id: plan.id,
        status: plan.status,
        trial_threshold: plan.trial_threshold,
        trial_revenue: plan.trial_revenue,
        trial_usage_records_count: plan.trial_usage_records_count,
        subscription_status: plan.subscription_status,
        is_trial_active: plan.is_trial_active,
      })),
    });

    // Get billing events for history
    const billingEvents = await prisma.billing_events.findMany({
      where: {
        shop_id: shop, // This might need to be shop_domain too, let me check
      },
      orderBy: { occurred_at: "desc" },
      take: 20,
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
        billingEvents: [],
      });
    }

    // Debug logging
    console.log("🔍 Billing Plan Data:", {
      trial_threshold: billingPlan.trial_threshold,
      trial_revenue: billingPlan.trial_revenue,
      trial_usage_records_count: billingPlan.trial_usage_records_count,
      subscription_status: billingPlan.subscription_status,
      is_trial_active: billingPlan.is_trial_active,
      currency: shopCurrency,
    });

    // Map the billing plan data to the correct field names for the UI
    const updatedBillingPlan = {
      ...billingPlan,
      // Map database fields to UI field names
      attributed_revenue: Number(billingPlan.trial_revenue) || 0,
      usage_count: billingPlan.trial_usage_records_count || 0,
      currency: shopCurrency,
    };

    return json({ billingPlan: updatedBillingPlan, billingEvents });
  } catch (error) {
    console.error("Error loading billing data:", error);

    // Try to get shop currency even in error case
    let shopCurrency = "USD";
    try {
      const shopInfo = await prisma.shops.findUnique({
        where: { shop_domain: shop },
        select: { currency_code: true },
      });
      shopCurrency = shopInfo?.currency_code || "USD";
    } catch (e) {
      // Use USD as fallback
    }

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
      billingEvents: [],
    });
  }
}

export default function BillingTabsPage() {
  const { billingPlan, billingEvents } = useLoaderData<typeof loader>();
  const billingActions = useBillingActions();
  const [selectedTab, setSelectedTab] = useState(0);

  // Debug logging
  console.log("🔍 BillingTabsPage - Loaded Data:", {
    billingPlan,
    billingEvents: billingEvents?.length || 0,
  });

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
    {
      id: "events",
      content: "Events",
      panelID: "events-panel",
    },
  ];

  const renderOverview = () => {
    console.log("🔍 Render Overview - Billing Plan:", billingPlan);
    return (
      <BillingStatusRouter
        billingPlan={billingPlan}
        billingActions={billingActions}
      />
    );
  };

  const renderInvoices = () => {
    // Create billing data structure for the component
    const billingData = {
      recent_invoices: [], // We'll need to fetch this from database
      recent_events: billingEvents,
    };

    const formatCurrency = billingActions.formatCurrency;
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
        formatCurrency={formatCurrency}
        formatDate={formatDate}
        getStatusBadge={getStatusBadge}
      />
    );
  };

  const renderEvents = () => {
    // Create billing data structure for the component
    const billingData = {
      recent_events: billingEvents,
    };

    const formatDate = (date: string) => new Date(date).toLocaleDateString();

    return <BillingEvents billingData={billingData} formatDate={formatDate} />;
  };

  const renderTabContent = () => {
    switch (selectedTab) {
      case 0:
        return renderOverview();
      case 1:
        return renderInvoices();
      case 2:
        return renderEvents();
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
