import {
  BlockStack,
  Card,
  Text,
  Badge,
  Icon,
  InlineStack,
  Divider,
} from "@shopify/polaris";
import {
  ReceiptIcon,
  ClockIcon,
  CheckCircleIcon,
} from "@shopify/polaris-icons";

interface Invoice {
  id: string;
  invoice_number: string;
  status: string;
  total: number;
  subtotal: number;
  currency: string;
  period_start: string;
  period_end: string;
  due_date: string;
  paid_at?: string;
  created_at: string;
  shopify_charge_id?: string;
  billing_metadata?: any;
}

interface InvoicesHistoryProps {
  billingData: {
    recent_invoices: Invoice[];
  };
  formatCurrency: (amount: number | string, currency: string) => string;
  formatDate: (date: string | Date) => string;
  getStatusBadge: (status: string) => { tone: any; children: string };
}

export function InvoicesHistory({
  billingData,
  formatCurrency,
  formatDate,
  getStatusBadge,
}: InvoicesHistoryProps) {
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
          <Text as="h2" variant="headingLg" fontWeight="bold">
            Invoice History
          </Text>
          <div style={{ marginTop: "8px" }}>
            <Text as="p" variant="bodyMd" tone="subdued">
              Your billing invoices will appear here
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
            <Text as="h3" variant="headingLg" fontWeight="bold">
              No Invoices Yet
            </Text>
            <div style={{ marginTop: "12px" }}>
              <Text as="p" variant="bodyLg" tone="subdued">
                Invoices will appear here once billing charges are created at
                the end of each 30-day cycle.
              </Text>
            </div>
          </div>
        </Card>
      </BlockStack>
    );
  }

  return (
    <BlockStack gap="400">
      {/* Header */}
      <div
        style={{
          padding: "24px",
          backgroundColor: "#F8FAFC",
          borderRadius: "12px",
          border: "1px solid #E2E8F0",
        }}
      >
        <InlineStack align="space-between" blockAlign="center">
          <div>
            <Text as="h2" variant="headingLg" fontWeight="bold">
              Invoice History
            </Text>
            <div style={{ marginTop: "8px" }}>
              <Text as="p" variant="bodyMd" tone="subdued">
                {invoices.length} invoice{invoices.length !== 1 ? "s" : ""}{" "}
                total
              </Text>
            </div>
          </div>
        </InlineStack>
      </div>

      {/* Invoice Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(350px, 1fr))",
          gap: "16px",
        }}
      >
        {invoices.map((invoice) => {
          const statusBadge = getStatusBadge(invoice.status);
          const metadata = invoice.billing_metadata || {};

          return (
            <Card key={invoice.id}>
              <div style={{ padding: "20px" }}>
                <BlockStack gap="300">
                  {/* Invoice Header */}
                  <InlineStack align="space-between" blockAlign="center">
                    <BlockStack gap="100">
                      <Text as="h3" variant="headingMd" fontWeight="bold">
                        #{invoice.invoice_number}
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {formatDate(invoice.period_start)} -{" "}
                        {formatDate(invoice.period_end)}
                      </Text>
                    </BlockStack>
                    <Badge tone={statusBadge.tone}>
                      {statusBadge.children}
                    </Badge>
                  </InlineStack>

                  <Divider />

                  {/* Amount */}
                  <InlineStack align="space-between" blockAlign="center">
                    <Text as="p" variant="bodyMd" tone="subdued">
                      Total Amount
                    </Text>
                    <Text as="p" variant="headingLg" fontWeight="bold">
                      {formatCurrency(invoice.total, invoice.currency)}
                    </Text>
                  </InlineStack>

                  {/* Metadata Details */}
                  {metadata.purchases_count !== undefined && (
                    <div
                      style={{
                        padding: "12px",
                        backgroundColor: "#F8FAFC",
                        borderRadius: "8px",
                      }}
                    >
                      <BlockStack gap="100">
                        <InlineStack align="space-between">
                          <Text variant="bodySm" tone="subdued">
                            Purchases:
                          </Text>
                          <Text variant="bodySm" fontWeight="medium">
                            {formatCurrency(
                              metadata.purchases_total || 0,
                              invoice.currency,
                            )}{" "}
                            ({metadata.purchases_count || 0})
                          </Text>
                        </InlineStack>

                        {metadata.refunds_count > 0 && (
                          <InlineStack align="space-between">
                            <Text variant="bodySm" tone="subdued">
                              Total Refunds:
                            </Text>
                            <Text variant="bodySm" tone="critical">
                              -
                              {formatCurrency(
                                metadata.refunds_total || 0,
                                invoice.currency,
                              )}{" "}
                              ({metadata.refunds_count})
                            </Text>
                          </InlineStack>
                        )}

                        <Divider />

                        <InlineStack align="space-between">
                          <Text
                            variant="bodySm"
                            tone="subdued"
                            fontWeight="semibold"
                          >
                            Net Revenue:
                          </Text>
                          <Text variant="bodySm" fontWeight="bold">
                            {formatCurrency(
                              metadata.net_revenue || 0,
                              invoice.currency,
                            )}
                          </Text>
                        </InlineStack>
                      </BlockStack>
                    </div>
                  )}

                  {/* Cross-Period Refunds Section */}
                  {metadata.cross_period_refunds &&
                    metadata.cross_period_refunds.count > 0 && (
                      <div
                        style={{
                          padding: "12px",
                          backgroundColor: "#FEF3C7",
                          borderRadius: "8px",
                          border: "1px solid #FCD34D",
                        }}
                      >
                        <BlockStack gap="200">
                          <InlineStack gap="100" blockAlign="center">
                            <Text as="span">💡</Text>
                            <Text variant="bodySm" fontWeight="semibold">
                              Credits from Prior Periods
                            </Text>
                          </InlineStack>

                          <Text variant="bodySm" tone="subdued">
                            {metadata.cross_period_refunds.count} refund(s) from
                            previous billing periods were credited to this
                            cycle, reducing your bill.
                          </Text>

                          <InlineStack align="space-between">
                            <Text variant="bodySm">Total credit applied:</Text>
                            <Text
                              variant="bodySm"
                              fontWeight="medium"
                              tone="success"
                            >
                              -
                              {formatCurrency(
                                metadata.cross_period_refunds.total,
                                invoice.currency,
                              )}
                            </Text>
                          </InlineStack>

                          {/* Show which periods */}
                          {metadata.cross_period_refunds.details &&
                            metadata.cross_period_refunds.details.length >
                              0 && (
                              <div
                                style={{
                                  marginTop: "8px",
                                  paddingTop: "8px",
                                  borderTop: "1px solid #FCD34D",
                                }}
                              >
                                <Text
                                  variant="bodySm"
                                  tone="subdued"
                                  fontWeight="medium"
                                >
                                  From periods:
                                </Text>
                                <BlockStack gap="050">
                                  {metadata.cross_period_refunds.details
                                    .slice(0, 3)
                                    .map((refund: any, idx: number) => (
                                      <InlineStack
                                        key={idx}
                                        gap="100"
                                        align="space-between"
                                      >
                                        <Text variant="bodySm" tone="subdued">
                                          •{" "}
                                          {refund.purchase_period ||
                                            "Previous period"}
                                        </Text>
                                        <Text variant="bodySm" tone="subdued">
                                          -
                                          {formatCurrency(
                                            refund.amount,
                                            invoice.currency,
                                          )}
                                        </Text>
                                      </InlineStack>
                                    ))}
                                  {metadata.cross_period_refunds.details
                                    .length > 3 && (
                                    <Text variant="bodySm" tone="subdued">
                                      ... and{" "}
                                      {metadata.cross_period_refunds.details
                                        .length - 3}{" "}
                                      more
                                    </Text>
                                  )}
                                </BlockStack>
                              </div>
                            )}
                        </BlockStack>
                      </div>
                    )}

                  {/* Same Period Refunds Info */}
                  {metadata.same_period_refunds &&
                    metadata.same_period_refunds.count > 0 && (
                      <div
                        style={{
                          padding: "10px",
                          backgroundColor: "#F8FAFC",
                          borderRadius: "6px",
                        }}
                      >
                        <InlineStack align="space-between">
                          <Text variant="bodySm" tone="subdued">
                            Same-period refunds:
                          </Text>
                          <Text variant="bodySm" tone="subdued">
                            -
                            {formatCurrency(
                              metadata.same_period_refunds.total,
                              invoice.currency,
                            )}
                            ({metadata.same_period_refunds.count})
                          </Text>
                        </InlineStack>
                      </div>
                    )}

                  {/* Status Info */}
                  <div
                    style={{
                      padding: "10px",
                      backgroundColor:
                        invoice.status === "paid" ? "#ECFDF5" : "#FEF3C7",
                      borderRadius: "6px",
                      border: `1px solid ${invoice.status === "paid" ? "#BBF7D0" : "#FCD34D"}`,
                    }}
                  >
                    <InlineStack gap="200" blockAlign="center">
                      <Icon
                        source={
                          invoice.status === "paid"
                            ? CheckCircleIcon
                            : ClockIcon
                        }
                        tone="base"
                      />
                      <Text variant="bodySm">
                        {invoice.status === "paid"
                          ? `Paid on ${formatDate(invoice.paid_at || invoice.created_at)}`
                          : invoice.status === "pending"
                            ? `Due by ${formatDate(invoice.due_date)}`
                            : invoice.status === "no_charge"
                              ? "No charge (refunds exceeded sales)"
                              : "Status: " + invoice.status}
                      </Text>
                    </InlineStack>
                  </div>

                  {/* Shopify Charge ID */}
                  {invoice.shopify_charge_id && (
                    <Text variant="bodySm" tone="subdued" alignment="center">
                      Shopify Charge: {invoice.shopify_charge_id}
                    </Text>
                  )}
                </BlockStack>
              </div>
            </Card>
          );
        })}
      </div>
    </BlockStack>
  );
}
