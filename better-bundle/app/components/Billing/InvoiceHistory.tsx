import {
  BlockStack,
  Card,
  DataTable,
  Text,
  Badge,
  Icon,
  InlineStack,
} from "@shopify/polaris";
import { ReceiptIcon } from "@shopify/polaris-icons";

export function InvoicesHistory({
  billingData,
  formatCurrency,
  formatDate,
  getStatusBadge,
}: any) {
  const invoices = billingData?.recent_invoices || [];

  if (invoices.length === 0) {
    return (
      <BlockStack gap="400">
        <div
          style={{
            padding: "24px",
            backgroundColor: "#F8FAFC",
            borderRadius: "12px",
            border: "1px solid #E2E8F0",
          }}
        >
          <div style={{ color: "#1E293B" }}>
            <Text as="h2" variant="headingLg" fontWeight="bold">
              Recent Invoices
            </Text>
          </div>
          <div style={{ marginTop: "8px" }}>
            <Text as="p" variant="bodyMd" tone="subdued">
              View and track your billing history and payments
            </Text>
          </div>
        </div>

        <Card>
          <div
            style={{
              padding: "40px 32px",
              textAlign: "center",
            }}
          >
            <div
              style={{
                display: "inline-block",
                padding: "12px",
                backgroundColor: "#F8FAFC",
                borderRadius: "12px",
                marginBottom: "16px",
                border: "1px solid #E2E8F0",
              }}
            >
              <Icon source={ReceiptIcon} tone="base" />
            </div>
            <div style={{ color: "#1E293B" }}>
              <Text as="h3" variant="headingLg" fontWeight="bold">
                No Invoices Yet
              </Text>
            </div>
            <div style={{ marginTop: "12px" }}>
              <Text as="p" variant="bodyLg" tone="subdued">
                Invoices will appear here once your trial ends and billing
                begins. You'll receive detailed billing statements for your AI
                recommendation service.
              </Text>
            </div>
          </div>
        </Card>
      </BlockStack>
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

  const getStatusBadgeTone = (status: string) => {
    switch (status.toLowerCase()) {
      case "paid":
        return "success";
      case "pending":
      case "processing":
        return "warning";
      case "failed":
      case "overdue":
        return "critical";
      default:
        return "info";
    }
  };

  return (
    <BlockStack gap="400">
      <div
        style={{
          padding: "24px",
          backgroundColor: "#F8FAFC",
          borderRadius: "12px",
          border: "1px solid #E2E8F0",
        }}
      >
        <div style={{ color: "#1E293B" }}>
          <Text as="h2" variant="headingLg" fontWeight="bold">
            Recent Invoices
          </Text>
        </div>
        <div style={{ marginTop: "8px" }}>
          <Text as="p" variant="bodyMd" tone="subdued">
            View and track your billing history and payments
          </Text>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "16px",
        }}
      >
        {invoices.map((invoice: any, index: number) => (
          <Card key={invoice.id}>
            <div
              style={{
                padding: "20px",
                transition: "all 0.2s ease-in-out",
                cursor: "pointer",
                borderRadius: "8px",
                overflow: "hidden",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.boxShadow = "0 8px 25px rgba(0,0,0,0.1)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="center">
                  <BlockStack gap="100">
                    <Text
                      as="h3"
                      variant="headingSm"
                      tone="subdued"
                      fontWeight="medium"
                    >
                      Invoice #{invoice.invoice_number}
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      {formatDate(invoice.period_start)} - {formatDate(invoice.period_end)}
                    </Text>
                  </BlockStack>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      minWidth: "40px",
                      minHeight: "40px",
                      padding: "12px",
                      backgroundColor: "#3B82F615",
                      borderRadius: "16px",
                      border: "2px solid #3B82F630",
                    }}
                  >
                    <Icon source={ReceiptIcon} tone="base" />
                  </div>
                </InlineStack>

                <InlineStack align="space-between" blockAlign="center">
                  <div>
                    <Text as="p" variant="headingLg" fontWeight="bold" tone="success">
                      {formatCurrency(invoice.total, invoice.currency)}
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Due: {formatDate(invoice.due_date)}
                    </Text>
                  </div>
                  <Badge
                    tone={getStatusBadgeTone(invoice.status)}
                    size="small"
                  >
                    {invoice.status}
                  </Badge>
                </InlineStack>
              </BlockStack>
            </div>
          </Card>
        ))}
      </div>
    </BlockStack>
  );
}
