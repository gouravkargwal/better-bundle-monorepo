import {
  Badge,
  BlockStack,
  Button,
  Card,
  DataTable,
  EmptyState,
  InlineStack,
  Pagination,
  Text,
} from "@shopify/polaris";
import { NOTHING_FOUND } from "../../../components/UI/illustrations";
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

  const cycles = data?.cycles || [];
  const pagination = data?.pagination;

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

  const handlePageChange = (page: number) => {
    const newSearchParams = new URLSearchParams(searchParams);
    newSearchParams.set("page", page.toString());
    navigate(`?${newSearchParams.toString()}`);
  };

  const rows = cycles.map((cycle: any) => [
    `Cycle #${cycle.cycleNumber}`,
    cycle.startDate,
    cycle.endDate,
    getStatusBadge(cycle.status),
    cycle.commissionCount.toString(),
  ]);

  return (
    <Card>
      <div style={{ padding: "16px" }}>
        <InlineStack align="space-between">
          <Text variant="headingMd" as="h3">
            Billing cycles
          </Text>
          <Button
            loading={isLoading}
            onClick={() => {
              setIsLoading(true);
              setTimeout(() => setIsLoading(false), 1000);
            }}
          >
            Refresh
          </Button>
        </InlineStack>

        <div style={{ marginTop: "16px" }}>
          {cycles.length === 0 ? (
            <EmptyState
              heading="No billing cycles yet"
              image={NOTHING_FOUND}
            >
              <Text as="p">{data?.subscriptionType === "TRIAL" ||
                data?.subscriptionStatus === "TRIAL"
                  ? "Billing cycles will appear once your trial ends and subscription becomes active."
                  : "Billing cycles will appear once your subscription is active and you start generating commissions."}</Text>
            </EmptyState>
          ) : (
            <DataTable
              columnContentTypes={["text", "text", "text", "text", "text"]}
              headings={[
                "Cycle",
                "Start Date",
                "End Date",
                "Status",
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
