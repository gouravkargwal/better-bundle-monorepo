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

interface CommissionRecordsProps {
  shopId: string;
  shopCurrency: string;
  data?: any;
}

export function CommissionRecords({
  shopId,
  shopCurrency,
  data,
}: CommissionRecordsProps) {
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Get data from server
  const commissions = data?.commissions || [];
  const pagination = data?.pagination;
  const currency = data?.shopCurrency || shopCurrency || "USD";

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency,
    }).format(amount);
  };

  const formatPercentage = (rate: number) => {
    return `${(rate * 100).toFixed(1)}%`;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "recorded":
        return <Badge tone="success">Recorded</Badge>;
      case "pending":
        return <Badge tone="warning">Pending</Badge>;
      case "capped":
        return <Badge tone="info">Capped</Badge>;
      case "rejected":
        return <Badge tone="critical">Rejected</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const getPhaseBadge = (phase: string) => {
    switch (phase) {
      case "trial":
        return <Badge tone="info">Trial (Not Charged)</Badge>;
      case "paid":
        return <Badge tone="success">Charged</Badge>;
      default:
        return <Badge>{phase}</Badge>;
    }
  };

  const handlePageChange = (page: number) => {
    const newSearchParams = new URLSearchParams(searchParams);
    newSearchParams.set("page", page.toString());
    navigate(`?${newSearchParams.toString()}`);
  };

  const rows = commissions.map((commission: any, index: number) => [
    commission.orderId,
    commission.orderDate,
    formatCurrency(commission.attributedRevenue),
    formatPercentage(commission.commissionRate),
    commission.billingPhase === "trial"
      ? `${formatCurrency(commission.commissionEarned)} (Trial)`
      : formatCurrency(commission.commissionEarned),
    getPhaseBadge(commission.billingPhase),
  ]);

  return (
    <Card>
      <div style={{ padding: "16px" }}>
        <InlineStack align="space-between">
          <Text variant="headingMd" as="h3">
            💰 Commission Records
          </Text>
          <Button
            loading={isLoading}
            onClick={() => {
              setIsLoading(true);
              // Refresh commission data
              setTimeout(() => setIsLoading(false), 1000);
            }}
          >
            Refresh
          </Button>
        </InlineStack>

        <div style={{ marginTop: "16px" }}>
          {commissions.length === 0 ? (
            <div
              style={{
                padding: "48px 24px",
                textAlign: "center",
                backgroundColor: "#f8f9fa",
                borderRadius: "8px",
                border: "1px solid #e9ecef",
              }}
            >
              <div style={{ fontSize: "48px", marginBottom: "16px" }}>💰</div>
              <Text variant="headingMd" as="h4" tone="subdued">
                No Commission Records Found
              </Text>
              <Text as="p" tone="subdued" style={{ marginTop: "8px" }}>
                Commission records will appear here once your subscription is
                active and you start generating commissions.
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
                "Order ID",
                "Date",
                "Revenue",
                "Rate",
                "Commission",
                "Phase",
              ]}
              rows={rows}
              footerContent={`Showing ${commissions.length} of ${pagination?.totalCount || 0} commission records`}
            />
          )}
        </div>

        {commissions.length > 0 && pagination && pagination.totalPages > 1 && (
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
