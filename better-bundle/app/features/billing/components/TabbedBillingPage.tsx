import { Page, Tabs, BlockStack } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { useCallback, useMemo } from "react";
import { Outlet, useNavigate, useLocation } from "@remix-run/react";
import type { BillingState } from "../types/billing.types";
import { BillingPlan } from "./BillingPlan";
import { HeroHeader } from "../../../components/UI/HeroHeader";

interface TabbedBillingPageProps {
  shopId: string;
  shopCurrency: string;
  billingState: BillingState;
  subscriptionStatus?: string | null;
}

export function TabbedBillingPage({
  shopId,
  shopCurrency,
  billingState,
  subscriptionStatus,
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
        default:
          navigate("/app/billing");
      }
    },
    [navigate],
  );

  const tabs = [
    {
      id: "plan",
      content: "Billing plan",
      panelID: "plan-panel",
    },
    {
      id: "invoices",
      content: "Usage charges",
      panelID: "invoices-panel",
    },
    {
      id: "cycles",
      content: "Billing cycles",
      panelID: "cycles-panel",
    },
  ];

  // Determine which tab is active based on current route - memoized to prevent re-renders
  const activeTab = useMemo(() => {
    if (
      location.pathname === "/app/billing" ||
      location.pathname === "/app/billing/"
    )
      return 0;
    if (location.pathname.startsWith("/app/billing/invoices")) return 1;
    if (location.pathname.startsWith("/app/billing/cycles")) return 2;
    return 0;
  }, [location.pathname]);

  const renderTabContent = () => {
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
          title="Manage your plan and see what you've earned"
          subtitle="Review your billing plan, track usage charges, and check your billing cycle history — all in one place."
          variant="gradient"
          align="left"
        />

        <Tabs
          tabs={tabs}
          selected={activeTab}
          onSelect={handleTabChange}
          fitted
        >
          <div style={{ padding: "16px 0" }}>{renderTabContent()}</div>
        </Tabs>
      </BlockStack>
    </Page>
  );
}
