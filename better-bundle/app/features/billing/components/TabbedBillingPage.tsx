import { Page, Tabs, BlockStack } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { useState, useCallback } from "react";
import { Outlet, useNavigate, useLocation } from "@remix-run/react";
import type { BillingState } from "../types/billing.types";
import { BillingPlan } from "./BillingPlan";
import { HeroHeader } from "../../../components/UI/HeroHeader";

interface TabbedBillingPageProps {
  shopId: string;
  shopCurrency: string;
  billingState: BillingState;
}

export function TabbedBillingPage({
  shopId,
  shopCurrency,
  billingState,
}: TabbedBillingPageProps) {
  const navigate = useNavigate();
  const location = useLocation();

  const handleTabChange = useCallback(
    (selectedTabIndex: number) => {
      // Navigate to the appropriate resource route
      switch (selectedTabIndex) {
        case 0:
          navigate("/app/billing");
          break;
        case 1:
          navigate("/app/billing/invoices");
          break;
        case 2:
          navigate("/app/billing/cycles");
          break;
        case 3:
          navigate("/app/billing/commissions");
          break;
        default:
          navigate("/app/billing");
      }
    },
    [navigate],
  );

  const tabs = [
    {
      id: "plan",
      content: "💳 Billing Plan",
      panelID: "plan-panel",
    },
    {
      id: "invoices",
      content: "📄 Invoices",
      panelID: "invoices-panel",
    },
    {
      id: "cycles",
      content: "🔄 Billing Cycles",
      panelID: "cycles-panel",
    },
    {
      id: "commissions",
      content: "💰 Commission Records",
      panelID: "commissions-panel",
    },
  ];

  // Determine which tab is active based on current route
  const getActiveTab = () => {
    if (location.pathname === "/app/billing") return 0;
    if (location.pathname === "/app/billing/invoices") return 1;
    if (location.pathname === "/app/billing/cycles") return 2;
    if (location.pathname === "/app/billing/commissions") return 3;
    return 0;
  };

  const renderTabContent = () => {
    const activeTab = getActiveTab();

    switch (activeTab) {
      case 0:
        return (
          <BillingPlan
            shopId={shopId}
            shopCurrency={shopCurrency}
            billingState={billingState}
          />
        );
      default:
        return <Outlet />;
    }
  };

  return (
    <Page>
      <TitleBar title="Billing" />
      <BlockStack gap="300">
        <HeroHeader
          badge="💳 Billing Management"
          title="Billing & Commission"
          subtitle="Manage your billing plans, invoices, and commission records"
          gradient="green"
        />

        <Tabs
          tabs={tabs}
          selected={getActiveTab()}
          onSelect={handleTabChange}
          fitted
        >
          <div style={{ padding: "16px 0" }}>{renderTabContent()}</div>
        </Tabs>
      </BlockStack>
    </Page>
  );
}
