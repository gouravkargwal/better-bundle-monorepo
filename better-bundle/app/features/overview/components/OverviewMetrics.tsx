import {
  Card,
  Text,
  BlockStack,
  InlineStack,
  Icon,
  Badge,
} from "@shopify/polaris";
import { CashDollarIcon, ArrowUpIcon } from "@shopify/polaris-icons";
import { getCurrencySymbol } from "../../../utils/currency";

interface OverviewMetricsProps {
  overviewData: {
    totalRevenue: number;
    currency: string;
    conversionRate: number;
    revenueChange: number | null;
    conversionRateChange: number | null;
    phaseLabel: string;
    totalOrders: number;
    attributedOrders: number;
    activePlan: {
      name: string;
      type: string;
      description?: string;
      monthlyPrice: number;
      currency: string;
      status: string;
      startDate: Date;
      isActive: boolean;
    } | null;
  };
  isTrialPhase: boolean;
}

export function OverviewMetrics({
  overviewData,
  isTrialPhase,
}: OverviewMetricsProps) {
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

  const monthlyPrice = overviewData.activePlan?.monthlyPrice ?? 99;
  const amountPaid = isTrialPhase ? 0 : monthlyPrice;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
        gap: "12px",
      }}
    >
      {/* Total Revenue Generated Card */}
      <div
        style={{
          transition: "all 0.2s ease-in-out",
          cursor: "pointer",
          borderRadius: "16px",
          overflow: "hidden",
          height: "200px",
          display: "flex",
          flexDirection: "column",
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
          <div
            style={{
              padding: "12px",
              height: "180px",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <BlockStack gap="200">
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <Text
                    as="h4"
                    variant="headingSm"
                    tone="subdued"
                    fontWeight="medium"
                  >
                    💰 Total Revenue Generated
                  </Text>
                </BlockStack>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    minWidth: "44px",
                    minHeight: "44px",
                    padding: "10px",
                    backgroundColor: isTrialPhase ? "#F59E0B15" : "#10B98115",
                    borderRadius: "14px",
                    border: `2px solid ${isTrialPhase ? "#F59E0B30" : "#10B98130"}`,
                  }}
                >
                  <Icon source={CashDollarIcon} tone="base" />
                </div>
              </InlineStack>
              <div
                style={{
                  color: isTrialPhase ? "#F59E0B" : "#10B981",
                }}
              >
                <Text as="p" variant="heading2xl" fontWeight="bold">
                  {overviewData.totalRevenue > 0
                    ? formatCurrencyValue(
                        overviewData.totalRevenue,
                        overviewData.currency,
                      )
                    : "Ready to earn"}
                </Text>
              </div>
              <Text as="p" variant="bodySm" tone="subdued">
                {overviewData.totalRevenue > 0
                  ? isTrialPhase
                    ? "Revenue tracked during your free trial"
                    : "Revenue influenced by recommendations"
                  : "AI recommendations are active and tracking revenue"}
              </Text>
              {overviewData.revenueChange !== null && (
                <div>{getChangeBadge(overviewData.revenueChange)}</div>
              )}
            </BlockStack>
          </div>
        </Card>
      </div>

      {/* Cost Efficiency Card */}
      <div
        style={{
          transition: "all 0.2s ease-in-out",
          cursor: "pointer",
          borderRadius: "16px",
          overflow: "hidden",
          height: "200px",
          display: "flex",
          flexDirection: "column",
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
          <div
            style={{
              padding: "12px",
              height: "180px",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <BlockStack gap="200">
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <Text
                    as="h4"
                    variant="headingSm"
                    tone="subdued"
                    fontWeight="medium"
                  >
                    💡 Cost Efficiency
                  </Text>
                </BlockStack>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    minWidth: "44px",
                    minHeight: "44px",
                    padding: "10px",
                    backgroundColor: "#8B5CF615",
                    borderRadius: "14px",
                    border: "2px solid #8B5CF630",
                  }}
                >
                  <Icon source={ArrowUpIcon} tone="base" />
                </div>
              </InlineStack>
              <div style={{ color: "#8B5CF6" }}>
                <Text as="p" variant="heading2xl" fontWeight="bold">
                  {isTrialPhase
                    ? "Free Trial"
                    : formatCurrencyValue(monthlyPrice, overviewData.currency) +
                      "/mo"}
                </Text>
              </div>
              <Text as="p" variant="bodySm" tone="subdued">
                {overviewData.totalRevenue > 0 ? (
                  <>
                    You earned{" "}
                    {formatCurrencyValue(
                      overviewData.totalRevenue,
                      overviewData.currency,
                    )}
                    {!isTrialPhase && (
                      <>
                        , paid a flat{" "}
                        {formatCurrencyValue(
                          amountPaid,
                          overviewData.currency,
                        )}
                      </>
                    )}
                  </>
                ) : (
                  "No charges during your free trial"
                )}
              </Text>
              <div style={{ marginTop: "8px" }}>
                <Badge tone="success" size="small">
                  Flat monthly price
                </Badge>
              </div>
            </BlockStack>
          </div>
        </Card>
      </div>
    </div>
  );
}
