import { Card, Text, BlockStack, InlineStack, Icon } from "@shopify/polaris";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  StarFilledIcon,
  EyeCheckMarkIcon,
  CashDollarIcon,
  TeamIcon,
} from "@shopify/polaris-icons";
import type {
  DashboardOverview,
  AttributedMetrics,
  PerformanceMetrics,
} from "../../services/dashboard.service";
import { formatCurrency } from "../../utils/currency";

interface KPICardsProps {
  data: DashboardOverview;
  attributedMetrics: AttributedMetrics;
}

interface KPICardProps {
  title: string;
  value: string | number;
  change?: number | null;
  trend?: "up" | "down" | "neutral";
  icon?: React.ReactNode;
  color?: string;
  description?: string;
}

function KPICard({
  title,
  value,
  change,
  trend,
  icon,
  color = "#3B82F6",
  description,
}: KPICardProps) {
  console.log(`KPICard ${title}:`, { value, change, trend });
  const getTrendColor = () => {
    if (trend === "up") return "success";
    if (trend === "down") return "critical";
    return "info";
  };

  return (
    <div
      style={{
        transition: "all 0.2s ease-in-out",
        cursor: "pointer",
        borderRadius: "8px",
        overflow: "hidden",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = "translateY(-4px)";
        e.currentTarget.style.boxShadow = "0 12px 30px rgba(0,0,0,0.15)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "translateY(0)";
        e.currentTarget.style.boxShadow = "none";
      }}
    >
      <Card>
        <div style={{ minHeight: "120px", padding: "4px" }}>
          <BlockStack gap="300">
            <InlineStack align="space-between" blockAlign="center">
              <BlockStack gap="100">
                <Text
                  as="h3"
                  variant="headingSm"
                  tone="subdued"
                  fontWeight="medium"
                >
                  {title}
                </Text>
                {description && (
                  <Text as="p" variant="bodySm" tone="subdued">
                    {description}
                  </Text>
                )}
              </BlockStack>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  minWidth: "40px",
                  minHeight: "40px",
                  padding: "12px",
                  backgroundColor: color + "15",
                  borderRadius: "16px",
                  border: `2px solid ${color}30`,
                  transition: "all 0.2s ease-in-out",
                }}
              >
                {icon}
              </div>
            </InlineStack>

            <InlineStack align="space-between" blockAlign="center">
              <div style={{ color: color }}>
                <Text as="p" variant="headingLg" fontWeight="bold">
                  {value}
                </Text>
              </div>

              {change !== undefined && change !== null && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    fontWeight: "600",
                    fontSize: "12px",
                    padding: "4px 8px",
                    backgroundColor:
                      trend === "up"
                        ? "#10B98115"
                        : trend === "down"
                          ? "#EF444415"
                          : change === null
                            ? "#3B82F615"
                            : "#6B728015",
                    borderRadius: "6px",
                    border: `1px solid ${trend === "up" ? "#10B98130" : trend === "down" ? "#EF444430" : change === null ? "#3B82F630" : "#6B728030"}`,
                    transition: "all 0.2s ease-in-out",
                  }}
                >
                  <Icon
                    source={
                      trend === "up"
                        ? ArrowUpIcon
                        : trend === "down"
                          ? ArrowDownIcon
                          : ArrowUpIcon
                    }
                    tone={getTrendColor()}
                  />
                  <span
                    style={{
                      color:
                        trend === "up"
                          ? "#10B981"
                          : trend === "down"
                            ? "#EF4444"
                            : change === null
                              ? "#3B82F6"
                              : "#6B7280",
                      fontWeight: "700",
                    }}
                  >
                    {`${change > 0 ? "+" : ""}${change.toFixed(1)}%`}
                  </span>
                </div>
              )}
            </InlineStack>
          </BlockStack>
        </div>
      </Card>
    </div>
  );
}

export function KPICards({ data, attributedMetrics }: KPICardsProps) {
  const formatCurrencyAmount = (amount: number) => {
    return formatCurrency(amount, data.currency_code);
  };

  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  return (
    <BlockStack gap="400">
      <BlockStack gap="200">
        <Text as="h2" variant="headingLg">
          Extension Performance
        </Text>
        <Text as="p" variant="bodyMd" tone="subdued">
          Revenue and metrics generated by your recommendation extensions
        </Text>
      </BlockStack>

      {/* Revenue Section */}
      <BlockStack gap="200">
        <Text as="h3" variant="headingMd" tone="subdued">
          Revenue Impact
        </Text>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "12px",
            alignItems: "stretch",
          }}
        >
          <KPICard
            title="Attributed Revenue"
            value={formatCurrencyAmount(attributedMetrics.attributed_revenue)}
            change={data.revenue_change}
            trend={
              data.revenue_change !== null
                ? data.revenue_change >= 0
                  ? "up"
                  : "down"
                : "neutral"
            }
            icon={<Icon source={CashDollarIcon} tone="base" />}
            color="#10B981"
            description="Revenue from extensions"
          />
          <KPICard
            title="Attribution Rate"
            value={formatPercentage(attributedMetrics.attribution_rate)}
            icon={<Icon source={EyeCheckMarkIcon} tone="base" />}
            color="#3B82F6"
            description="% attributed to extensions"
          />
          <KPICard
            title="Net Revenue"
            value={formatCurrencyAmount(
              attributedMetrics.net_attributed_revenue,
            )}
            change={data.revenue_change}
            trend={
              data.revenue_change !== null
                ? data.revenue_change >= 0
                  ? "up"
                  : "down"
                : "neutral"
            }
            icon={<Icon source={StarFilledIcon} tone="base" />}
            color="#059669"
            description="After refunds"
          />
          <KPICard
            title="Attributed Refunds"
            value={formatCurrencyAmount(attributedMetrics.attributed_refunds)}
            icon={<Icon source={ArrowDownIcon} tone="base" />}
            color="#EF4444"
            description="Refunds from extensions"
          />
        </div>
      </BlockStack>

      {/* Performance Section */}
      <BlockStack gap="200">
        <Text as="h3" variant="headingMd" tone="subdued">
          Performance Metrics
        </Text>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "12px",
            alignItems: "stretch",
          }}
        >
          <KPICard
            title="Recommendations Shown"
            value={data.total_recommendations.toLocaleString()}
            change={data.recommendations_change}
            trend={
              data.recommendations_change !== null
                ? data.recommendations_change >= 0
                  ? "up"
                  : "down"
                : "neutral"
            }
            icon={<Icon source={EyeCheckMarkIcon} tone="base" />}
            color="#8B5CF6"
            description="Total impressions"
          />
          <KPICard
            title="Total Clicks"
            value={data.total_clicks.toLocaleString()}
            change={data.clicks_change}
            trend={
              data.clicks_change !== null
                ? data.clicks_change >= 0
                  ? "up"
                  : "down"
                : "neutral"
            }
            icon={<Icon source={StarFilledIcon} tone="base" />}
            color="#F59E0B"
            description="User clicks"
          />
          <KPICard
            title="Conversion Rate"
            value={formatPercentage(data.conversion_rate)}
            change={data.conversion_rate_change}
            trend={
              data.conversion_rate_change !== null
                ? data.conversion_rate_change >= 0
                  ? "up"
                  : "down"
                : "neutral"
            }
            color="#3B82F6"
            description="Click-to-purchase rate"
          />
          <KPICard
            title="Total Customers"
            value={data.total_customers.toLocaleString()}
            change={data.customers_change}
            trend={
              data.customers_change !== null
                ? data.customers_change >= 0
                  ? "up"
                  : "down"
                : "neutral"
            }
            icon={<Icon source={TeamIcon} tone="base" />}
            color="#06B6D4"
            description="Active customers"
          />
          <KPICard
            title="Average Order Value"
            value={formatCurrencyAmount(data.average_order_value)}
            change={data.aov_change}
            trend={
              data.aov_change !== null
                ? data.aov_change >= 0
                  ? "up"
                  : "down"
                : "neutral"
            }
            icon={<Icon source={StarFilledIcon} tone="base" />}
            color="#EF4444"
            description="Per order value"
          />
        </div>
      </BlockStack>
    </BlockStack>
  );
}

// Revenue-focused component
export function RevenueKPICards({ data, attributedMetrics }: KPICardsProps) {
  const formatCurrencyAmount = (amount: number) => {
    return formatCurrency(amount, data.currency_code);
  };

  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  return (
    <BlockStack gap="500">
      <BlockStack gap="300">
        <div
          style={{
            padding: "24px",
            backgroundColor: "#F8FAFC",
            borderRadius: "12px",
            border: "1px solid #E2E8F0",
          }}
        >
          <div style={{ color: "#1E293B" }}>
            <Text as="h2" variant="headingLg" fontWeight="bold">
              💰 Revenue Analytics
            </Text>
          </div>
          <div style={{ marginTop: "8px" }}>
            <Text as="p" variant="bodyMd" tone="subdued">
              Revenue generated by your recommendation extensions
            </Text>
          </div>
        </div>
      </BlockStack>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "20px",
          alignItems: "stretch",
          padding: "8px",
        }}
      >
        <KPICard
          title="Attributed Revenue"
          value={formatCurrencyAmount(attributedMetrics.attributed_revenue)}
          icon={<Icon source={CashDollarIcon} tone="base" />}
          color="#10B981"
          description="Revenue from extensions"
        />
        <KPICard
          title="Attribution Rate"
          value={formatPercentage(attributedMetrics.attribution_rate)}
          icon={<Icon source={EyeCheckMarkIcon} tone="base" />}
          color="#3B82F6"
          description="% attributed to extensions"
        />
        <KPICard
          title="Net Revenue"
          value={formatCurrencyAmount(attributedMetrics.net_attributed_revenue)}
          icon={<Icon source={StarFilledIcon} tone="base" />}
          color="#059669"
          description="After refunds"
        />
        <KPICard
          title="Attributed Refunds"
          value={formatCurrencyAmount(attributedMetrics.attributed_refunds)}
          icon={<Icon source={ArrowDownIcon} tone="base" />}
          color="#EF4444"
          description="Refunds from extensions"
        />
        <KPICard
          title="Average Order Value"
          value={formatCurrencyAmount(data.average_order_value)}
          change={data.aov_change}
          trend={
            data.aov_change !== null
              ? data.aov_change >= 0
                ? "up"
                : "down"
              : "neutral"
          }
          icon={<Icon source={StarFilledIcon} tone="base" />}
          color="#EF4444"
          description="Per order value"
        />
      </div>
    </BlockStack>
  );
}

// Performance-focused component
export function PerformanceKPICards({ data }: { data: PerformanceMetrics }) {
  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  return (
    <BlockStack gap="500">
      <BlockStack gap="300">
        <div
          style={{
            padding: "24px",
            backgroundColor: "#F0F9FF",
            borderRadius: "12px",
            border: "1px solid #BAE6FD",
          }}
        >
          <div style={{ color: "#0C4A6E" }}>
            <Text as="h2" variant="headingLg" fontWeight="bold">
              📊 Performance Metrics
            </Text>
          </div>
          <div style={{ marginTop: "8px" }}>
            <Text as="p" variant="bodyMd" tone="subdued">
              How your recommendation extensions are performing
            </Text>
          </div>
        </div>
      </BlockStack>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "20px",
          alignItems: "stretch",
          padding: "8px",
        }}
      >
        <KPICard
          title="Recommendations Shown"
          value={data.total_recommendations.toLocaleString()}
          change={data.recommendations_change}
          trend={
            data.recommendations_change !== null
              ? data.recommendations_change >= 0
                ? "up"
                : "down"
              : "neutral"
          }
          icon={<Icon source={EyeCheckMarkIcon} tone="base" />}
          color="#8B5CF6"
          description="Total impressions"
        />
        <KPICard
          title="Total Clicks"
          value={data.total_clicks.toLocaleString()}
          change={data.clicks_change}
          trend={
            data.clicks_change !== null
              ? data.clicks_change >= 0
                ? "up"
                : "down"
              : "neutral"
          }
          icon={<Icon source={StarFilledIcon} tone="base" />}
          color="#F59E0B"
          description="User clicks"
        />
        <KPICard
          title="Conversion Rate"
          value={formatPercentage(data.conversion_rate)}
          change={data.conversion_rate_change}
          trend={
            data.conversion_rate_change !== null
              ? data.conversion_rate_change >= 0
                ? "up"
                : "down"
              : "neutral"
          }
          color="#3B82F6"
          description="Click-to-purchase rate"
        />
        <KPICard
          title="Total Customers"
          value={data.total_customers.toLocaleString()}
          change={data.customers_change}
          trend={
            data.customers_change !== null
              ? data.customers_change >= 0
                ? "up"
                : "down"
              : "neutral"
          }
          icon={<Icon source={TeamIcon} tone="base" />}
          color="#06B6D4"
          description="Active customers"
        />
      </div>
    </BlockStack>
  );
}
