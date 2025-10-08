// features/overview/components/OverviewMetrics.tsx
import {
  Card,
  Text,
  BlockStack,
  InlineStack,
  Icon,
  Badge,
} from "@shopify/polaris";
import { CashDollarIcon, EyeCheckMarkIcon } from "@shopify/polaris-icons";
import { getCurrencySymbol } from "../../../utils/currency";

interface OverviewMetricsProps {
  overviewData: {
    totalRevenue: number;
    currency: string;
    conversionRate: number;
    revenueChange: number | null;
    conversionRateChange: number | null;
    isTrialPhase: boolean;
    phaseLabel: string;
    phaseDescription: string;
  };
}

export function OverviewMetrics({ overviewData }: OverviewMetricsProps) {
  const formatCurrencyValue = (amount: number, currencyCode: string) => {
    const symbol = getCurrencySymbol(currencyCode);
    const numericAmount = Math.abs(amount);
    return `${symbol}${numericAmount.toFixed(2)}`;
  };

  const getChangeBadge = (change: number | null) => {
    if (change === null) return null;
    const isPositive = change > 0;
    return (
      <Badge tone={isPositive ? "success" : "critical"} size="small">
        {`${isPositive ? "+" : "-"}${change.toFixed(1)}%`}
      </Badge>
    );
  };

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
        gap: "24px",
      }}
    >
      {/* Revenue Card */}
      <div
        style={{
          transition: "all 0.2s ease-in-out",
          cursor: "pointer",
          borderRadius: "16px",
          overflow: "hidden",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = "translateY(-2px)";
          e.currentTarget.style.boxShadow = "0 8px 25px rgba(0,0,0,0.1)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = "translateY(0)";
          e.currentTarget.style.boxShadow = "none";
        }}
      >
        <Card>
          <div style={{ padding: "20px" }}>
            <BlockStack gap="200">
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <Text
                    as="h4"
                    variant="headingSm"
                    tone="subdued"
                    fontWeight="medium"
                  >
                    {overviewData.phaseLabel}
                  </Text>
                </BlockStack>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    minWidth: "48px",
                    minHeight: "48px",
                    padding: "12px",
                    backgroundColor: overviewData.isTrialPhase
                      ? "#F59E0B15"
                      : "#10B98115",
                    borderRadius: "12px",
                    border: `2px solid ${overviewData.isTrialPhase ? "#F59E0B30" : "#10B98130"}`,
                  }}
                >
                  <Icon source={CashDollarIcon} tone="base" />
                </div>
              </InlineStack>
              <div
                style={{
                  color: overviewData.isTrialPhase ? "#F59E0B" : "#10B981",
                }}
              >
                <Text as="p" variant="heading2xl" fontWeight="bold">
                  {formatCurrencyValue(
                    overviewData.totalRevenue,
                    overviewData.currency,
                  )}
                </Text>
              </div>
              <Text as="p" variant="bodySm" tone="subdued">
                {overviewData.phaseDescription}
              </Text>
              {overviewData.revenueChange !== null && (
                <div>{getChangeBadge(overviewData.revenueChange)}</div>
              )}
            </BlockStack>
          </div>
        </Card>
      </div>

      {/* Conversion Rate Card */}
      <div
        style={{
          transition: "all 0.2s ease-in-out",
          cursor: "pointer",
          borderRadius: "16px",
          overflow: "hidden",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = "translateY(-2px)";
          e.currentTarget.style.boxShadow = "0 8px 25px rgba(0,0,0,0.1)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = "translateY(0)";
          e.currentTarget.style.boxShadow = "none";
        }}
      >
        <Card>
          <div style={{ padding: "20px" }}>
            <BlockStack gap="200">
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <Text
                    as="h4"
                    variant="headingSm"
                    tone="subdued"
                    fontWeight="medium"
                  >
                    Conversion Rate
                  </Text>
                </BlockStack>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    minWidth: "48px",
                    minHeight: "48px",
                    padding: "12px",
                    backgroundColor: "#3B82F615",
                    borderRadius: "12px",
                    border: "2px solid #3B82F630",
                  }}
                >
                  <Icon source={EyeCheckMarkIcon} tone="base" />
                </div>
              </InlineStack>
              <div style={{ color: "#3B82F6" }}>
                <Text as="p" variant="heading2xl" fontWeight="bold">
                  {overviewData.conversionRate.toFixed(1)}%
                </Text>
              </div>
              {overviewData.conversionRateChange !== null && (
                <div>{getChangeBadge(overviewData.conversionRateChange)}</div>
              )}
            </BlockStack>
          </div>
        </Card>
      </div>
    </div>
  );
}
