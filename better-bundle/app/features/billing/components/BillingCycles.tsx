import {
  Card,
  Text,
  DataTable,
  Badge,
  Button,
  InlineStack,
  ProgressBar,
  Pagination,
} from "@shopify/polaris";
import { useState } from "react";
import { useNavigate, useSearchParams } from "@remix-run/react";

interface BillingCyclesProps {
  shopId: string;
  shopCurrency: string;
  data?: any;
}

export function BillingCycles({
  shopId,
  shopCurrency,
  data,
}: BillingCyclesProps) {
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Get data from server
  const cycles = data?.cycles || [];
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
      case "active":
        return <Badge tone="info">Active</Badge>;
      case "completed":
        return <Badge tone="success">Completed</Badge>;
      case "cancelled":
        return <Badge tone="critical">Cancelled</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const getUsagePercentage = (usage: number, cap: number) => {
    return Math.min((usage / cap) * 100, 100);
  };

  const handlePageChange = (page: number) => {
    const newSearchParams = new URLSearchParams(searchParams);
    newSearchParams.set("page", page.toString());
    navigate(`?${newSearchParams.toString()}`);
  };

  const rows = cycles.map((cycle: any, index: number) => [
    `Cycle #${cycle.cycleNumber}`,
    cycle.startDate,
    cycle.endDate,
    getStatusBadge(cycle.status),
    formatCurrency(cycle.usageAmount),
    formatCurrency(cycle.capAmount),
    <div style={{ width: "100px" }}>
      <ProgressBar
        progress={getUsagePercentage(cycle.usageAmount, cycle.capAmount)}
        size="small"
      />
    </div>,
    cycle.commissionCount.toString(),
  ]);

  return (
    <Card>
      <div style={{ padding: "16px" }}>
        <InlineStack align="space-between">
          <Text variant="headingMd" as="h3">
            🔄 Billing Cycles
          </Text>
          <Button
            loading={isLoading}
            onClick={() => {
              setIsLoading(true);
              // Refresh cycles data
              setTimeout(() => setIsLoading(false), 1000);
            }}
          >
            Refresh
          </Button>
        </InlineStack>

        <div style={{ marginTop: "16px" }}>
          {cycles.length === 0 ? (
            <div
              style={{
                padding: "48px 24px",
                textAlign: "center",
                backgroundColor: "#f8f9fa",
                borderRadius: "8px",
                border: "1px solid #e9ecef",
              }}
            >
              <div style={{ fontSize: "48px", marginBottom: "16px" }}>📊</div>
              <Text variant="headingMd" as="h4" tone="subdued">
                No Billing Cycles Found
              </Text>
              <Text as="p" tone="subdued" style={{ marginTop: "8px" }}>
                Billing cycles will appear here once your subscription is active
                and you start generating commissions.
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
                "text",
                "text",
              ]}
              headings={[
                "Cycle",
                "Start Date",
                "End Date",
                "Status",
                "Usage",
                "Cap",
                "Progress",
                "Commissions",
              ]}
              rows={rows}
              footerContent={`Showing ${cycles.length} of ${pagination?.totalCount || 0} billing cycles`}
            />
          )}
        </div>

        {cycles.length > 0 && pagination && pagination.totalPages > 1 && (
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
