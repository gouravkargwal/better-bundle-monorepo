import { BlockStack, Card, DataTable, Text } from "@shopify/polaris";

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
