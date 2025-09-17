import React, { useState, useEffect } from "react";
import {
  Card,
  Text,
  BlockStack,
  InlineStack,
  Button,
  Badge,
  DataTable,
  Spinner,
  Banner,
  Box,
  Icon,
} from "@shopify/polaris";
import {
  CashDollarIcon,
  CalendarIcon,
  ReceiptIcon,
  AlertTriangleIcon,
} from "@shopify/polaris-icons";

interface BillingData {
  billing_plan: {
    id: string;
    name: string;
    type: string;
    status: string;
    configuration: any;
    effective_from: string;
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
  current_metrics: {
    total_revenue: number;
    attributed_revenue: number;
    billable_revenue: number;
    total_interactions: number;
    total_conversions: number;
    conversion_rate: number;
    calculated_fee: number;
    final_fee: number;
  } | null;
}

interface BillingSummary {
  summary: {
    total_revenue: number;
    total_fees: number;
    average_monthly_revenue: number;
    average_monthly_fee: number;
    average_fee_rate: number;
    months_analyzed: number;
  };
  monthly_breakdown: Array<{
    period_start: string;
    period_end: string;
    revenue: number;
    fee: number;
    currency: string;
  }>;
}

export function BillingDashboard() {
  const [billingData, setBillingData] = useState<BillingData | null>(null);
  const [billingSummary, setBillingSummary] = useState<BillingSummary | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadBillingData();
  }, []);

  const loadBillingData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Load billing status
      const billingResponse = await fetch("/api/billing");
      const billingResult = await billingResponse.json();

      if (!billingResult.success) {
        throw new Error(billingResult.error || "Failed to load billing data");
      }

      setBillingData(billingResult.data);

      // Load billing summary
      const summaryResponse = await fetch("/api/billing", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          action: "get_billing_summary",
          data: { months: 12 },
        }),
      });

      const summaryResult = await summaryResponse.json();
      if (summaryResult.success) {
        setBillingSummary(summaryResult.data);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load billing data",
      );
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number, currency: string = "USD") => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency,
    }).format(amount);
  };

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
          <Text as="p">No billing information available.</Text>
        </Banner>
      </Box>
    );
  }

  return (
    <BlockStack gap="400">
      {/* Billing Plan Status */}
      <Card>
        <BlockStack gap="300">
          <InlineStack align="space-between">
            <Text as="h2" variant="headingLg">
              Billing Plan
            </Text>
            {billingData.billing_plan &&
              getStatusBadge(billingData.billing_plan.status)}
          </InlineStack>

          {billingData.billing_plan ? (
            <BlockStack gap="200">
              <Text as="p" variant="bodyMd">
                <strong>Plan:</strong> {billingData.billing_plan.name}
              </Text>
              <Text as="p" variant="bodyMd">
                <strong>Type:</strong>{" "}
                {billingData.billing_plan.type.replace("_", " ").toUpperCase()}
              </Text>
              <Text as="p" variant="bodyMd">
                <strong>Effective:</strong>{" "}
                {formatDate(billingData.billing_plan.effective_from)}
              </Text>
            </BlockStack>
          ) : (
            <Banner tone="warning">
              <Text as="p">
                No active billing plan found. Please contact support.
              </Text>
            </Banner>
          )}
        </BlockStack>
      </Card>

      {/* Current Month Metrics */}
      {billingData.current_metrics && (
        <Card>
          <BlockStack gap="300">
            <Text as="h2" variant="headingLg">
              Current Month Performance
            </Text>

            <InlineStack gap="400" wrap={false}>
              <Box
                padding="300"
                background="bg-surface-secondary"
                borderRadius="200"
                minWidth="200px"
              >
                <BlockStack gap="100">
                  <InlineStack gap="200" align="center">
                    <Icon source={CashDollarIcon} tone="base" />
                    <Text as="p" variant="bodyMd" tone="subdued">
                      Attributed Revenue
                    </Text>
                  </InlineStack>
                  <Text as="p" variant="headingLg">
                    {formatCurrency(
                      billingData.current_metrics.attributed_revenue,
                    )}
                  </Text>
                </BlockStack>
              </Box>

              <Box
                padding="300"
                background="bg-surface-secondary"
                borderRadius="200"
                minWidth="200px"
              >
                <BlockStack gap="100">
                  <InlineStack gap="200" align="center">
                    <Icon source={ReceiptIcon} tone="base" />
                    <Text as="p" variant="bodyMd" tone="subdued">
                      Your Fee (3%)
                    </Text>
                  </InlineStack>
                  <Text as="p" variant="headingLg">
                    {formatCurrency(billingData.current_metrics.final_fee)}
                  </Text>
                </BlockStack>
              </Box>

              <Box
                padding="300"
                background="bg-surface-secondary"
                borderRadius="200"
                minWidth="200px"
              >
                <BlockStack gap="100">
                  <InlineStack gap="200" align="center">
                    <Icon source={CalendarIcon} tone="base" />
                    <Text as="p" variant="bodyMd" tone="subdued">
                      Conversion Rate
                    </Text>
                  </InlineStack>
                  <Text as="p" variant="headingLg">
                    {(
                      billingData.current_metrics.conversion_rate * 100
                    ).toFixed(1)}
                    %
                  </Text>
                </BlockStack>
              </Box>
            </InlineStack>
          </BlockStack>
        </Card>
      )}

      {/* Billing Summary */}
      {billingSummary && (
        <Card>
          <BlockStack gap="300">
            <Text as="h2" variant="headingLg">
              Billing Summary (Last 12 Months)
            </Text>

            <InlineStack gap="400" wrap={false}>
              <Box
                padding="300"
                background="bg-surface-secondary"
                borderRadius="200"
                minWidth="200px"
              >
                <BlockStack gap="100">
                  <Text as="p" variant="bodyMd" tone="subdued">
                    Total Revenue
                  </Text>
                  <Text as="p" variant="headingLg">
                    {formatCurrency(billingSummary.summary.total_revenue)}
                  </Text>
                </BlockStack>
              </Box>

              <Box
                padding="300"
                background="bg-surface-secondary"
                borderRadius="200"
                minWidth="200px"
              >
                <BlockStack gap="100">
                  <Text as="p" variant="bodyMd" tone="subdued">
                    Total Fees
                  </Text>
                  <Text as="p" variant="headingLg">
                    {formatCurrency(billingSummary.summary.total_fees)}
                  </Text>
                </BlockStack>
              </Box>

              <Box
                padding="300"
                background="bg-surface-secondary"
                borderRadius="200"
                minWidth="200px"
              >
                <BlockStack gap="100">
                  <Text as="p" variant="bodyMd" tone="subdued">
                    Average Fee Rate
                  </Text>
                  <Text as="p" variant="headingLg">
                    {billingSummary.summary.average_fee_rate.toFixed(1)}%
                  </Text>
                </BlockStack>
              </Box>
            </InlineStack>
          </BlockStack>
        </Card>
      )}

      {/* Recent Invoices */}
      <Card>
        <BlockStack gap="300">
          <Text as="h2" variant="headingLg">
            Recent Invoices
          </Text>

          {billingData.recent_invoices.length > 0 ? (
            <DataTable
              columnContentTypes={["text", "text", "text", "text", "text"]}
              headings={["Invoice #", "Period", "Amount", "Status", "Due Date"]}
              rows={billingData.recent_invoices.map((invoice) => [
                invoice.invoice_number,
                `${formatDate(invoice.period_start)} - ${formatDate(invoice.period_end)}`,
                formatCurrency(invoice.total, invoice.currency),
                getStatusBadge(invoice.status),
                formatDate(invoice.due_date),
              ])}
            />
          ) : (
            <Banner>
              <Text as="p">No invoices found.</Text>
            </Banner>
          )}
        </BlockStack>
      </Card>

      {/* Recent Events */}
      <Card>
        <BlockStack gap="300">
          <Text as="h2" variant="headingLg">
            Recent Billing Events
          </Text>

          {billingData.recent_events.length > 0 ? (
            <DataTable
              columnContentTypes={["text", "text", "text"]}
              headings={["Event", "Description", "Date"]}
              rows={billingData.recent_events.map((event) => [
                event.type.replace(/_/g, " ").toUpperCase(),
                getEventDescription(event),
                formatDate(event.occurred_at),
              ])}
            />
          ) : (
            <Banner>
              <Text as="p">No recent events found.</Text>
            </Banner>
          )}
        </BlockStack>
      </Card>
    </BlockStack>
  );
}

function getEventDescription(event: any): string {
  switch (event.type) {
    case "plan_created":
      return "Billing plan created";
    case "plan_updated":
      return "Billing plan updated";
    case "metrics_calculated":
      return "Monthly metrics calculated";
    case "invoice_generated":
      return "Invoice generated";
    case "payment_received":
      return "Payment received";
    case "payment_failed":
      return "Payment failed";
    case "shopify_webhook_received":
      return "Shopify webhook received";
    default:
      return "Billing event";
  }
}
