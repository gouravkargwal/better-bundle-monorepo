import React, { useState, useEffect, useCallback } from "react";
import {
  Card,
  Text,
  BlockStack,
  InlineStack,
  Button,
  Badge,
  Spinner,
  Banner,
  Box,
  Icon,
  Tabs,
  DataTable,
  ProgressBar,
} from "@shopify/polaris";
import { CheckIcon } from "@shopify/polaris-icons";
import { default as getCurrencySymbol } from "currency-symbol-map";

interface BillingData {
  billing_plan: {
    id: string;
    name: string;
    type: string;
    status: string;
    configuration: any;
    effective_from: string;
    currency?: string;
    trial_status: {
      is_trial_active: boolean;
      trial_threshold: number;
      trial_revenue: number;
      remaining_revenue: number;
      trial_progress: number;
    };
  } | null;
  recent_invoices: Array<{
    id: string;
    invoice_number: string;
    status: string;
    total: number;
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

export function BillingDashboard() {
  const [billingData, setBillingData] = useState<BillingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTab, setSelectedTab] = useState(0);

  useEffect(() => {
    loadBillingData();
  }, []);

  const loadBillingData = async () => {
    try {
      setLoading(true);
      setError(null);

      console.log("Loading billing data...");

      // Load billing status
      const billingResponse = await fetch("/api/billing");
      const billingResult = await billingResponse.json();

      console.log("Billing API response:", billingResult);

      if (!billingResult.success) {
        throw new Error(billingResult.error || "Failed to load billing data");
      }

      setBillingData(billingResult.data);
      console.log("Billing data set:", billingResult.data);
    } catch (err) {
      console.error("Error loading billing data:", err);
      setError(
        err instanceof Error ? err.message : "Failed to load billing data",
      );
    } finally {
      setLoading(false);
    }
  };

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

  if (loading) {
    return (
      <Box padding="400">
        <InlineStack align="center">
          <Spinner size="large" />
          <Text as="p">Loading billing information...</Text>
        </InlineStack>
      </Box>
    );
  }

  if (error) {
    return (
      <Box padding="400">
        <Banner tone="critical">
          <Text as="p">{error}</Text>
          <Button onClick={loadBillingData}>Try Again</Button>
        </Banner>
      </Box>
    );
  }

  if (!billingData) {
    return (
      <Box padding="400">
        <Banner>
          <Text as="p">
            No billing information available. Please refresh the page or contact
            support if this persists.
          </Text>
        </Banner>
      </Box>
    );
  }

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
      case 2: // Billing Events
        return (
          <BillingEvents billingData={billingData} formatDate={formatDate} />
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

function BillingStatus({
  billingData,
  formatCurrency,
  getStatusBadge,
  formatDate,
}: any) {
  if (!billingData?.billing_plan) {
    return (
      <Banner tone="warning">
        <Text as="p">No billing plan found. Please contact support.</Text>
      </Banner>
    );
  }

  const plan = billingData.billing_plan;
  const trialStatus = plan.trial_status;

  // Ensure trial status values are numbers
  const safeTrialStatus = {
    is_trial_active: trialStatus?.is_trial_active || false,
    trial_threshold: Number(trialStatus?.trial_threshold) || 0,
    trial_revenue: Number(trialStatus?.trial_revenue) || 0,
    remaining_revenue: Math.max(
      0,
      (Number(trialStatus?.trial_threshold) || 0) -
        (Number(trialStatus?.trial_revenue) || 0),
    ),
    trial_progress:
      trialStatus?.trial_threshold > 0
        ? ((Number(trialStatus?.trial_revenue) || 0) /
            (Number(trialStatus?.trial_threshold) || 1)) *
          100
        : 0,
  };

  return (
    <BlockStack gap="500">
      {/* Billing Plan Overview */}
      <div
        style={{
          padding: "32px",
          background: "linear-gradient(135deg, #1e40af 0%, #3730a3 100%)",
          borderRadius: "16px",
          color: "white",
        }}
      >
        <BlockStack gap="400">
          <InlineStack align="space-between" blockAlign="center">
            <div>
              <div style={{ color: "white" }}>
                <Text as="h2" variant="headingLg" fontWeight="bold">
                  💳 {plan.name}
                </Text>
              </div>
              <div style={{ color: "white", opacity: 0.9 }}>
                <Text as="p" variant="bodyLg">
                  {plan.type.replace("_", " ").toUpperCase()} Plan
                </Text>
              </div>
            </div>
            {getStatusBadge(plan.status)}
          </InlineStack>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "20px",
            }}
          >
            <div>
              <div style={{ color: "white", opacity: 0.8 }}>
                <Text as="p" variant="bodySm">
                  Effective Date
                </Text>
              </div>
              <div style={{ color: "white" }}>
                <Text as="p" variant="headingMd" fontWeight="bold">
                  {formatDate(plan.effective_from)}
                </Text>
              </div>
            </div>
            <div>
              <div style={{ color: "white", opacity: 0.8 }}>
                <Text as="p" variant="bodySm">
                  Currency
                </Text>
              </div>
              <div style={{ color: "white" }}>
                <Text as="p" variant="headingMd" fontWeight="bold">
                  {plan.currency || "USD"}
                </Text>
              </div>
            </div>
            <div>
              <div style={{ color: "white", opacity: 0.8 }}>
                <Text as="p" variant="bodySm">
                  Revenue Share Rate
                </Text>
              </div>
              <div style={{ color: "white" }}>
                <Text as="p" variant="headingMd" fontWeight="bold">
                  3%
                </Text>
              </div>
            </div>
          </div>
        </BlockStack>
      </div>

      {/* Trial Status */}
      {safeTrialStatus.is_trial_active ? (
        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="400">
              <div
                style={{
                  padding: "20px",
                  backgroundColor: "#F0F9FF",
                  borderRadius: "12px",
                  border: "1px solid #BAE6FD",
                }}
              >
                <BlockStack gap="300">
                  <InlineStack align="space-between" blockAlign="center">
                    <Text as="h3" variant="headingMd" fontWeight="bold">
                      🎉 Free Trial Active
                    </Text>
                    <Badge>
                      {`${Math.round(safeTrialStatus.trial_progress)}% Complete`}
                    </Badge>
                  </InlineStack>

                  <Text as="p" variant="bodyMd" tone="subdued">
                    Generate{" "}
                    {formatCurrency(
                      safeTrialStatus.remaining_revenue,
                      plan.currency,
                    )}{" "}
                    more in attributed revenue to start billing
                  </Text>

                  <ProgressBar
                    progress={safeTrialStatus.trial_progress}
                    size="large"
                  />

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns:
                        "repeat(auto-fit, minmax(150px, 1fr))",
                      gap: "16px",
                    }}
                  >
                    <div>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Current Revenue
                      </Text>
                      <Text as="p" variant="headingMd" fontWeight="bold">
                        {formatCurrency(
                          safeTrialStatus.trial_revenue,
                          plan.currency,
                        )}
                      </Text>
                    </div>
                    <div>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Trial Threshold
                      </Text>
                      <Text as="p" variant="headingMd" fontWeight="bold">
                        {formatCurrency(
                          safeTrialStatus.trial_threshold,
                          plan.currency,
                        )}
                      </Text>
                      <Text as="p" variant="bodyXs" tone="subdued">
                        (Equivalent to $200 USD)
                      </Text>
                    </div>
                    <div>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Remaining
                      </Text>
                      <Text as="p" variant="headingMd" fontWeight="bold">
                        {formatCurrency(
                          safeTrialStatus.remaining_revenue,
                          plan.currency,
                        )}
                      </Text>
                    </div>
                  </div>
                </BlockStack>
              </div>
            </BlockStack>
          </div>
        </Card>
      ) : (
        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="400">
              <div
                style={{
                  padding: "20px",
                  backgroundColor: "#F0FDF4",
                  borderRadius: "12px",
                  border: "1px solid #BBF7D0",
                }}
              >
                <BlockStack gap="300">
                  <InlineStack align="space-between" blockAlign="center">
                    <Text as="h3" variant="headingMd" fontWeight="bold">
                      💰 Trial Completed - Billing Active
                    </Text>
                    <Badge tone="success">Paid Plan</Badge>
                  </InlineStack>

                  <Text as="p" variant="bodyMd" tone="subdued">
                    Your trial has ended. You're now being charged 3% of
                    attributed revenue.
                  </Text>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns:
                        "repeat(auto-fit, minmax(150px, 1fr))",
                      gap: "16px",
                    }}
                  >
                    <div>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Trial Revenue
                      </Text>
                      <Text as="p" variant="headingMd" fontWeight="bold">
                        {formatCurrency(
                          safeTrialStatus.trial_revenue,
                          plan.currency,
                        )}
                      </Text>
                    </div>
                    <div>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Billing Rate
                      </Text>
                      <Text as="p" variant="headingMd" fontWeight="bold">
                        3%
                      </Text>
                    </div>
                    <div>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Status
                      </Text>
                      <Text as="p" variant="headingMd" fontWeight="bold">
                        Active
                      </Text>
                    </div>
                  </div>
                </BlockStack>
              </div>
            </BlockStack>
          </div>
        </Card>
      )}
    </BlockStack>
  );
}

// ============= INVOICES HISTORY COMPONENT =============

function InvoicesHistory({
  billingData,
  formatCurrency,
  formatDate,
  getStatusBadge,
}: any) {
  const invoices = billingData?.recent_invoices || [];

  if (invoices.length === 0) {
    return (
      <Card>
        <div style={{ padding: "32px", textAlign: "center" }}>
          <Text as="h3" variant="headingMd" fontWeight="bold">
            📄 No Invoices Yet
          </Text>
          <div style={{ marginTop: "12px" }}>
            <Text as="p" variant="bodyMd" tone="subdued">
              Invoices will appear here once your trial ends and billing begins.
            </Text>
          </div>
        </div>
      </Card>
    );
  }

  const invoiceRows = invoices.map((invoice: any) => [
    invoice.invoice_number,
    formatDate(invoice.period_start),
    formatDate(invoice.period_end),
    formatCurrency(invoice.total, invoice.currency),
    getStatusBadge(invoice.status),
    formatDate(invoice.due_date),
  ]);

  return (
    <BlockStack gap="400">
      <Card>
        <div style={{ padding: "24px" }}>
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd" fontWeight="bold">
              📄 Recent Invoices
            </Text>

            <DataTable
              columnContentTypes={[
                "text",
                "text",
                "text",
                "text",
                "text",
                "text",
              ]}
              headings={[
                "Invoice #",
                "Period Start",
                "Period End",
                "Amount",
                "Status",
                "Due Date",
              ]}
              rows={invoiceRows}
            />
          </BlockStack>
        </div>
      </Card>
    </BlockStack>
  );
}

function BillingEvents({ billingData, formatDate }: any) {
  const events = billingData?.recent_events || [];

  if (events.length === 0) {
    return (
      <Card>
        <div style={{ padding: "32px", textAlign: "center" }}>
          <Text as="h3" variant="headingMd" fontWeight="bold">
            📋 No Billing Events
          </Text>
          <div style={{ marginTop: "12px" }}>
            <Text as="p" variant="bodyMd" tone="subdued">
              Billing events will appear here as they occur.
            </Text>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <BlockStack gap="400">
      <Card>
        <div style={{ padding: "24px" }}>
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd" fontWeight="bold">
              📋 Recent Billing Events
            </Text>

            <BlockStack gap="300">
              {events.map((event: any, index: number) => (
                <div
                  key={event.id}
                  style={{
                    padding: "16px",
                    backgroundColor: "#F8FAFC",
                    borderRadius: "8px",
                    border: "1px solid #E2E8F0",
                  }}
                >
                  <InlineStack align="space-between" blockAlign="center">
                    <BlockStack gap="100">
                      <Text as="p" variant="bodyMd" fontWeight="medium">
                        {event.type.replace(/_/g, " ").toUpperCase()}
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {formatDate(event.occurred_at)}
                      </Text>
                    </BlockStack>
                    <Icon source={CheckIcon} tone="base" />
                  </InlineStack>
                </div>
              ))}
            </BlockStack>
          </BlockStack>
        </div>
      </Card>
    </BlockStack>
  );
}
