import {
  BlockStack,
  Card,
  DataTable,
  Text,
  Badge,
  Icon,
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
      <Card>
        <div
          style={{
            padding: "40px 32px",
            textAlign: "center",
            background: "linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%)",
            borderRadius: "16px",
            border: "1px solid #E2E8F0",
          }}
        >
          <div
            style={{
              display: "inline-block",
              padding: "12px",
              backgroundColor: "#3B82F615",
              borderRadius: "12px",
              marginBottom: "16px",
            }}
          >
            <Icon source={ReceiptIcon} tone="base" />
          </div>
          <div style={{ color: "#1E293B" }}>
            <Text as="h3" variant="headingLg" fontWeight="bold">
              📄 No Invoices Yet
            </Text>
          </div>
          <div style={{ marginTop: "12px" }}>
            <Text as="p" variant="bodyLg" tone="subdued">
              Invoices will appear here once your trial ends and billing begins.
              You'll receive detailed billing statements for your AI
              recommendation service.
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
    <BlockStack gap="300">
      <Card>
        <div style={{ padding: "20px" }}>
          <BlockStack gap="300">
            <div
              style={{
                padding: "20px",
                backgroundColor: "#F0F9FF",
                borderRadius: "12px",
                border: "1px solid #BAE6FD",
              }}
            >
              <div style={{ color: "#0C4A6E" }}>
                <Text as="h3" variant="headingMd" fontWeight="bold">
                  📄 Recent Invoices
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
                backgroundColor: "#FFFFFF",
                borderRadius: "12px",
                border: "1px solid #E2E8F0",
                boxShadow:
                  "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)",
                overflow: "hidden",
              }}
            >
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
                rows={invoiceRows.map((row: any, index: number) => [
                  <div
                    key={`invoice-${index}`}
                    style={{ fontWeight: "600", color: "#1E293B" }}
                  >
                    {row[0]}
                  </div>,
                  <div key={`start-${index}`} style={{ color: "#64748B" }}>
                    {row[1]}
                  </div>,
                  <div key={`end-${index}`} style={{ color: "#64748B" }}>
                    {row[2]}
                  </div>,
                  <div
                    key={`amount-${index}`}
                    style={{ fontWeight: "600", color: "#059669" }}
                  >
                    {row[3]}
                  </div>,
                  <div key={`status-${index}`}>
                    <Badge
                      tone={getStatusBadgeTone(
                        row[4]?.props?.children || row[4],
                      )}
                      size="small"
                    >
                      {row[4]?.props?.children || row[4]}
                    </Badge>
                  </div>,
                  <div key={`due-${index}`} style={{ color: "#64748B" }}>
                    {row[5]}
                  </div>,
                ])}
              />
            </div>
          </BlockStack>
        </div>
      </Card>
    </BlockStack>
  );
}
