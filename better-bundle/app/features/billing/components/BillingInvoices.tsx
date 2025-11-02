import {
  Card,
  Text,
  DataTable,
  Badge,
  Button,
  InlineStack,
  Pagination,
  BlockStack,
} from "@shopify/polaris";
import { useState, useCallback } from "react";
import { useNavigate, useSearchParams, useRevalidator } from "@remix-run/react";
import { DateRangePicker } from "../../../components/UI/DateRangePicker";

interface BillingInvoicesProps {
  shopId: string;
  shopCurrency: string;
  shopDomain?: string;
  data?: any;
}

export function BillingInvoices({
  shopId,
  shopCurrency,
  shopDomain,
  data,
}: BillingInvoicesProps) {
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const revalidator = useRevalidator();
  const [searchParams] = useSearchParams();

  const handleViewOrder = (orderId: string) => {
    window.open(`shopify://admin/orders/${orderId}`, "_top");
  };

  // Get data from server
  const invoices = data?.invoices || [];
  const pagination = data?.pagination;
  const currency = data?.shopCurrency || shopCurrency || "USD";
  const filters = data?.filters || {};

  // Date filter state - default to last 30 days
  const getDefaultStartDate = () => {
    const date = new Date();
    date.setDate(date.getDate() - 30);
    return date.toISOString().split("T")[0];
  };

  const [startDate, setStartDate] = useState(
    filters.startDate || getDefaultStartDate(),
  );
  const [endDate, setEndDate] = useState(
    filters.endDate || new Date().toISOString().split("T")[0],
  );

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

  const onSearchParamsChange = useCallback(
    (newParams: URLSearchParams) => {
      // Reset to page 1 when filters change
      newParams.set("page", "1");
      navigate(`?${newParams.toString()}`);
    },
    [navigate],
  );

  const handleDateChange = useCallback(
    (range: { startDate: string; endDate: string }) => {
      setStartDate(range.startDate);
      setEndDate(range.endDate);

      const newSearchParams = new URLSearchParams(searchParams);
      newSearchParams.set("startDate", range.startDate);
      newSearchParams.set("endDate", range.endDate);
      onSearchParamsChange(newSearchParams);
    },
    [searchParams, onSearchParamsChange],
  );

  const handleClearFilters = () => {
    const newSearchParams = new URLSearchParams(searchParams);
    newSearchParams.delete("startDate");
    newSearchParams.delete("endDate");
    newSearchParams.set("page", "1");
    setStartDate(getDefaultStartDate());
    setEndDate(new Date().toISOString().split("T")[0]);
    navigate(`?${newSearchParams.toString()}`);
  };

  const hasActiveFilters = filters.startDate || filters.endDate;

  // Helper to extract numeric ID from Shopify GID format
  const extractNumericId = (gid: string): string => {
    // Shopify GID format: gid://shopify/AppUsageRecord/539543896182
    // Extract just the numeric part for cleaner display
    const parts = gid.split("/");
    const numericId = parts[parts.length - 1];
    return numericId || gid;
  };

  const rows = invoices.map((invoice: any, index: number) => [
    <div key={`id-${index}`}>
      <Text as="span" variant="bodyMd">
        {extractNumericId(invoice.id)}
      </Text>
      <div style={{ marginTop: "2px" }}>
        <Text as="span" variant="bodySm" tone="subdued">
          {invoice.id}
        </Text>
      </div>
    </div>,
    invoice.date,
    formatCurrency(invoice.amount),
    getStatusBadge(invoice.status),
    <div key={`desc-${index}`}>
      <Text as="span" variant="bodyMd">
        {invoice.description || "Usage charge"}
      </Text>
      {invoice.orderIds && invoice.orderIds.length > 0 && (
        <div style={{ marginTop: "4px" }}>
          <Text as="span" variant="bodySm" tone="subdued">
            Orders:{" "}
            {invoice.orderIds.length <= 5
              ? invoice.orderIds.join(", ")
              : `${invoice.orderIds.slice(0, 5).join(", ")} (+${invoice.orderIds.length - 5} more)`}
          </Text>
          {invoice.totalRevenue && (
            <div style={{ marginTop: "2px" }}>
              <Text as="span" variant="bodySm" tone="subdued">
                Revenue: {formatCurrency(invoice.totalRevenue)}
              </Text>
            </div>
          )}
        </div>
      )}
    </div>,
    <div key={`action-${index}`}>
      {invoice.orderIds && invoice.orderIds.length > 0 ? (
        <InlineStack gap="200" align="start">
          {invoice.orderIds.slice(0, 3).map((orderId: string, idx: number) => (
            <Button
              key={`order-${orderId}-${idx}`}
              variant="plain"
              onClick={() => handleViewOrder(orderId)}
            >
              View Order
            </Button>
          ))}
          {invoice.orderIds.length > 3 && (
            <Text as="span" variant="bodySm" tone="subdued">
              +{invoice.orderIds.length - 3} more
            </Text>
          )}
        </InlineStack>
      ) : (
        <Text as="span" tone="subdued" variant="bodyMd">
          —
        </Text>
      )}
    </div>,
  ]);

  return (
    <BlockStack gap="400">
      <Card>
        <div style={{ padding: "16px" }}>
          <BlockStack gap="400">
            <InlineStack align="space-between">
              <Text variant="headingMd" as="h3">
                📄 Usage Records
              </Text>
              <InlineStack gap="200">
                {hasActiveFilters && (
                  <Button onClick={handleClearFilters} size="slim">
                    Clear Filters
                  </Button>
                )}
                <Button
                  loading={isLoading || revalidator.state === "loading"}
                  onClick={() => {
                    setIsLoading(true);
                    // Use Remix's revalidator to refresh data without full page reload
                    revalidator.revalidate();
                    setTimeout(() => setIsLoading(false), 500);
                  }}
                >
                  Refresh
                </Button>
              </InlineStack>
            </InlineStack>

            {/* Date Filter */}
            <InlineStack gap="300" align="start">
              <div>
                <Text as="span" variant="bodyMd" fontWeight="semibold">
                  Filter by date:{" "}
                </Text>
                <DateRangePicker
                  startDate={startDate}
                  endDate={endDate}
                  onDateChange={handleDateChange}
                  maxDate={new Date().toISOString().split("T")[0]}
                />
              </div>
            </InlineStack>

            <div style={{ marginTop: "8px" }}>
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
                  <div style={{ fontSize: "48px", marginBottom: "16px" }}>
                    📄
                  </div>
                  <Text variant="headingMd" as="h4" tone="subdued">
                    No Records Found
                  </Text>
                  <Text as="p" tone="subdued">
                    {hasActiveFilters
                      ? "No usage records found for the selected date range. Try adjusting your filters."
                      : "Usage records will appear here once your subscription is active and you start generating usage charges."}
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
                    "Record ID",
                    "Date",
                    "Amount",
                    "Status",
                    "Description",
                    "Actions",
                  ]}
                  rows={rows}
                  footerContent={`Showing ${invoices.length} of ${pagination?.totalCount || 0} usage records`}
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
          </BlockStack>
        </div>
      </Card>
    </BlockStack>
  );
}
