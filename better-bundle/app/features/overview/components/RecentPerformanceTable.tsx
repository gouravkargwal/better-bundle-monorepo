// features/overview/components/RecentPerformanceTable.tsx
import {
  Card,
  Text,
  BlockStack,
  DataTable,
  Badge,
  InlineStack,
} from "@shopify/polaris";
import { getCurrencySymbol } from "../../../utils/currency";

interface RecentPerformanceTableProps {
  performanceData: {
    topBundles: Array<{
      id: string;
      name: string;
      revenue: number;
      orders: number;
      conversionRate: number;
    }>;
    revenueByType: Array<{
      type: string;
      revenue: number;
      percentage: number;
    }>;
    trends: {
      weeklyGrowth: number;
      monthlyGrowth: number;
    };
  };
  currency: string;
}

export function RecentPerformanceTable({
  performanceData,
  currency,
}: RecentPerformanceTableProps) {
  const formatCurrencyValue = (amount: number, currencyCode: string) => {
    const symbol = getCurrencySymbol(currencyCode);
    const numericAmount = Math.abs(amount);
    return `${symbol}${numericAmount.toFixed(2)}`;
  };

  const getChangeBadge = (change: number) => {
    const isPositive = change > 0;
    return (
      <Badge tone={isPositive ? "success" : "critical"} size="small">
        {`${isPositive ? "+" : ""}${change.toFixed(1)}%`}
      </Badge>
    );
  };

  // Prepare data for the top bundles table
  const topBundlesRows =
    performanceData.topBundles.length > 0
      ? performanceData.topBundles.map((bundle) => [
          bundle.name,
          formatCurrencyValue(bundle.revenue, currency),
          bundle.orders.toString(),
          `${bundle.conversionRate.toFixed(1)}%`,
          "-", // No individual bundle growth data available
        ])
      : [["No bundle data available", "-", "-", "-", "-"]];

  const topBundlesHeadings = [
    "Bundle Name",
    "Revenue Generated",
    "Orders",
    "Revenue Share",
    "Growth",
  ];

  // If no data, show empty state like billing pages
  if (
    performanceData.topBundles.length === 0 &&
    performanceData.revenueByExtension.length === 0
  ) {
    return (
      <Card>
        <div style={{ padding: "16px" }}>
          <div
            style={{
              padding: "48px 24px",
              textAlign: "center",
              backgroundColor: "#f8f9fa",
              borderRadius: "8px",
              border: "1px solid #e9ecef",
            }}
          >
            <div style={{ fontSize: "48px", marginBottom: "16px" }}>📈</div>
            <Text variant="headingMd" as="h4" tone="subdued">
              No Performance Data Yet
            </Text>
            <Text as="p" tone="subdued" style={{ marginTop: "8px" }}>
              Performance metrics will appear here once customers start
              purchasing through your AI recommendations.
            </Text>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div style={{ padding: "16px" }}>
        <BlockStack gap="300">
          {/* Header */}
          <div>
            <Text as="h3" variant="headingLg" fontWeight="bold">
              📈 Recent Performance
            </Text>
            <Text as="p" variant="bodyMd" tone="subdued">
              Top performing product bundles and revenue trends
            </Text>
          </div>

          {/* Performance Overview Cards */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "16px",
            }}
          >
            <div
              style={{
                padding: "12px",
                backgroundColor: "#F0F9FF",
                borderRadius: "6px",
                border: "1px solid #BAE6FD",
              }}
            >
              <Text as="p" variant="bodySm" tone="subdued">
                Weekly Growth
              </Text>
              <Text as="p" variant="headingMd" fontWeight="bold">
                {performanceData.trends.weeklyGrowth !== 0
                  ? getChangeBadge(performanceData.trends.weeklyGrowth)
                  : "0%"}
              </Text>
            </div>
            <div
              style={{
                padding: "12px",
                backgroundColor: "#F0FDF4",
                borderRadius: "6px",
                border: "1px solid #BBF7D0",
              }}
            >
              <Text as="p" variant="bodySm" tone="subdued">
                Monthly Growth
              </Text>
              <Text as="p" variant="headingMd" fontWeight="bold">
                {performanceData.trends.monthlyGrowth !== 0
                  ? getChangeBadge(performanceData.trends.monthlyGrowth)
                  : "0%"}
              </Text>
            </div>
            <div
              style={{
                padding: "12px",
                backgroundColor: "#FEF3C7",
                borderRadius: "6px",
                border: "1px solid #FDE68A",
              }}
            >
              <Text as="p" variant="bodySm" tone="subdued">
                Top Bundle
              </Text>
              <Text as="p" variant="headingMd" fontWeight="bold">
                {performanceData.topBundles.length > 0
                  ? performanceData.topBundles[0].name
                  : "No data"}
              </Text>
            </div>
          </div>

          {/* Top Performing Bundles Table */}
          <div>
            <Text
              as="h4"
              variant="headingMd"
              fontWeight="semibold"
              style={{ marginBottom: "16px" }}
            >
              🏆 Top Performing Bundles
            </Text>
            <DataTable
              columnContentTypes={["text", "text", "text", "text", "text"]}
              headings={topBundlesHeadings}
              rows={topBundlesRows}
              footerContent={`Showing ${performanceData.topBundles.length} top performing bundles`}
            />
          </div>

          {/* Revenue by Extension */}
          <div>
            <Text
              as="h4"
              variant="headingMd"
              fontWeight="semibold"
              style={{ marginBottom: "16px" }}
            >
              📍 Revenue by Extension
            </Text>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
                gap: "12px",
              }}
            >
              {performanceData.revenueByExtension &&
              performanceData.revenueByExtension.length > 0 ? (
                performanceData.revenueByExtension.map((extension, index) => (
                  <div
                    key={index}
                    style={{
                      padding: "12px",
                      backgroundColor: "#F8FAFC",
                      borderRadius: "6px",
                      border: "1px solid #E2E8F0",
                    }}
                  >
                    <InlineStack align="space-between" blockAlign="center">
                      <div>
                        <Text as="p" variant="bodyMd" fontWeight="medium">
                          {extension.type}
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          {formatCurrencyValue(extension.revenue, currency)}
                        </Text>
                      </div>
                      <Badge tone="info" size="small">
                        {extension.percentage.toFixed(1)}%
                      </Badge>
                    </InlineStack>
                  </div>
                ))
              ) : (
                <div
                  style={{
                    padding: "12px",
                    backgroundColor: "#F8FAFC",
                    borderRadius: "6px",
                    border: "1px solid #E2E8F0",
                    textAlign: "center",
                  }}
                >
                  <Text as="p" variant="bodySm" tone="subdued">
                    No extension data available
                  </Text>
                </div>
              )}
            </div>
          </div>
        </BlockStack>
      </div>
    </Card>
  );
}
