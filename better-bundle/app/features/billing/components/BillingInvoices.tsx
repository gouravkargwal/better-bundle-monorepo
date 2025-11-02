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
import { useNavigate, useSearchParams } from "@remix-run/react";
import { DateRangePicker } from "../../../components/UI/DateRangePicker";

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

  const rows = invoices.map((invoice: any, index: number) => [
    <div key={`id-${index}`}>
      <Text as="span" variant="bodyMd">
        {invoice.id.length > 30
          ? `${invoice.id.substring(0, 30)}...`
          : invoice.id}
      </Text>
    </div>,
    invoice.date,
    formatCurrency(invoice.amount),
    getStatusBadge(invoice.status),
    invoice.description || "—",
    <Text as="span" tone="subdued" variant="bodyMd" key={`action-${index}`}>
      —
    </Text>,
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
                  loading={isLoading}
                  onClick={() => {
                    setIsLoading(true);
                    window.location.reload();
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
