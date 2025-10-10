import {
  Card,
  Text,
  DataTable,
  Badge,
  Button,
  InlineStack,
  Pagination,
} from "@shopify/polaris";
import { useState } from "react";
import { useNavigate, useSearchParams } from "@remix-run/react";

interface BillingInvoicesProps {
  shopId: string;
  shopCurrency: string;
  data?: any;
}

export function BillingInvoices({
  shopId,
  shopCurrency,
  data,
}: BillingInvoicesProps) {
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Get data from server
  const invoices = data?.invoices || [];
  const pagination = data?.pagination;
  const currency = data?.shopCurrency || shopCurrency || "USD";

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency,
    }).format(amount);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "paid":
        return <Badge tone="success">Paid</Badge>;
      case "pending":
        return <Badge tone="warning">Pending</Badge>;
      case "overdue":
        return <Badge tone="critical">Overdue</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const handlePageChange = (page: number) => {
    const newSearchParams = new URLSearchParams(searchParams);
    newSearchParams.set("page", page.toString());
    navigate(`?${newSearchParams.toString()}`);
  };

  const rows = invoices.map((invoice: any, index: number) => [
    invoice.id,
    invoice.date,
    formatCurrency(invoice.amount),
    getStatusBadge(invoice.status),
    invoice.description,
    <Button
      size="slim"
      onClick={() => {
        // Handle download/view invoice
        console.log("Download invoice:", invoice.id);
      }}
    >
      Download
    </Button>,
  ]);

  return (
    <Card>
      <div style={{ padding: "16px" }}>
        <InlineStack align="space-between">
          <Text variant="headingMd" as="h3">
            📄 Billing Invoices
          </Text>
          <Button
            loading={isLoading}
            onClick={() => {
              setIsLoading(true);
              // Refresh invoices data
              setTimeout(() => setIsLoading(false), 1000);
            }}
          >
            Refresh
          </Button>
        </InlineStack>

        <div style={{ marginTop: "16px" }}>
          {invoices.length === 0 ? (
            <div
              style={{
                padding: "48px 24px",
                textAlign: "center",
                backgroundColor: "#f8f9fa",
                borderRadius: "8px",
                border: "1px solid #e9ecef",
              }}
            >
              <div style={{ fontSize: "48px", marginBottom: "16px" }}>📄</div>
              <Text variant="headingMd" as="h4" tone="subdued">
                No Invoices Found
              </Text>
              <Text as="p" tone="subdued" style={{ marginTop: "8px" }}>
                Invoices will appear here once your subscription is active and
                you start generating commissions.
              </Text>
            </div>
          ) : (
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
                "Invoice ID",
                "Date",
                "Amount",
                "Status",
                "Description",
                "Actions",
              ]}
              rows={rows}
              footerContent={`Showing ${invoices.length} of ${pagination?.totalCount || 0} invoices`}
            />
          )}
        </div>

        {invoices.length > 0 && pagination && pagination.totalPages > 1 && (
          <div
            style={{
              marginTop: "16px",
              display: "flex",
              justifyContent: "center",
            }}
          >
            <Pagination
              hasPrevious={pagination.hasPrevious}
              onPrevious={() => handlePageChange(pagination.page - 1)}
              hasNext={pagination.hasNext}
              onNext={() => handlePageChange(pagination.page + 1)}
            />
          </div>
        )}
      </div>
    </Card>
  );
}
