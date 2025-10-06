import { useState, useCallback } from "react";
import { BlockStack, Badge, Tabs } from "@shopify/polaris";
import { default as getCurrencySymbol } from "currency-symbol-map";
import { BillingStatus } from "./BillingStatus";
import { InvoicesHistory } from "./InvoiceHistory";

interface BillingData {
  billing_plan: {
    id: string;
    name: string;
    type: string;
    status: string;
    configuration: any;
    effective_from: string;
    currency: string;
    trial_status: {
      is_trial_active?: boolean;
      trial_threshold?: number;
      trial_revenue?: number;
      remaining_revenue: number;
      trial_progress: number;
    };
  };
  recent_invoices: Array<{
    id: string;
    invoice_number: string;
    status: string;
    total: string;
    currency: string;
    period_start: string;
    period_end: string;
    due_date: string;
    created_at: string;
  }>;
  recent_events: Array<{
    id: string;
    type: string;
    data: any;
    occurred_at: string;
  }>;
}

interface BillingDashboardProps {
  billingData: BillingData;
}

export function BillingDashboard({ billingData }: BillingDashboardProps) {
  const [selectedTab, setSelectedTab] = useState(0);

  const handleTabChange = useCallback((selectedTabIndex: number) => {
    setSelectedTab(selectedTabIndex);
  }, []);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case "paid":
        return <Badge tone="success">Paid</Badge>;
      case "pending":
        return <Badge tone="warning">Pending</Badge>;
      case "overdue":
        return <Badge tone="critical">Overdue</Badge>;
      case "active":
        return <Badge tone="success">Active</Badge>;
      case "inactive":
        return <Badge tone="info">Inactive</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const formatCurrency = (
    amount: number | string | null | undefined,
    currencyCode: string = "USD",
  ) => {
    // Handle null, undefined, or non-numeric values
    if (amount === null || amount === undefined || amount === "") {
      return `${getCurrencySymbol(currencyCode)}0.00`;
    }

    // Convert to number if it's a string
    const numericAmount =
      typeof amount === "string" ? parseFloat(amount) : amount;

    // Check if the conversion resulted in a valid number
    if (isNaN(numericAmount)) {
      return `${getCurrencySymbol(currencyCode)}0.00`;
    }

    const symbol = getCurrencySymbol(currencyCode);
    return `${symbol}${numericAmount.toFixed(2)}`;
  };

  const tabs = [
    {
      id: "billing-status",
      content: "💳 Billing Status",
      panelID: "billing-status-panel",
    },
    {
      id: "invoices",
      content: "📄 Invoices & Payments",
      panelID: "invoices-panel",
    },
    {
      id: "billing-history",
      content: "📋 Billing Events",
      panelID: "billing-history-panel",
    },
  ];

  const renderTabContent = () => {
    switch (selectedTab) {
      case 0: // Billing Status
        return (
          <BillingStatus
            billingData={billingData}
            formatCurrency={formatCurrency}
            getStatusBadge={getStatusBadge}
            formatDate={formatDate}
          />
        );
      case 1: // Invoices
        return (
          <InvoicesHistory
            billingData={billingData}
            formatCurrency={formatCurrency}
            formatDate={formatDate}
            getStatusBadge={getStatusBadge}
          />
        );
      default:
        return null;
    }
  };

  return (
    <BlockStack gap="500">
      <Tabs tabs={tabs} selected={selectedTab} onSelect={handleTabChange}>
        {renderTabContent()}
      </Tabs>
    </BlockStack>
  );
}
