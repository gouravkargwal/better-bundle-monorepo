import { Card, Text, BlockStack, InlineStack, Icon } from "@shopify/polaris";
import { ArrowUpIcon, ArrowDownIcon } from "@shopify/polaris-icons";
import type { DashboardOverview } from "../../services/dashboard.service";
import { formatCurrency } from "../../utils/currency";

interface KPICardsProps {
  data: DashboardOverview;
}

interface KPICardProps {
  title: string;
  value: string | number;
  change?: number | null;
  trend?: "up" | "down" | "neutral";
  icon?: React.ReactNode;
}

function KPICard({ title, value, change, trend, icon }: KPICardProps) {
  const getTrendColor = () => {
    if (trend === "up") return "success";
    if (trend === "down") return "critical";
    return "subdued";
  };

  const getTrendIcon = () => {
    if (trend === "up") return <Icon source={ArrowUpIcon} tone="success" />;
    if (trend === "down")
      return <Icon source={ArrowDownIcon} tone="critical" />;
    return null;
  };

  return (
    <Card>
      <BlockStack gap="200">
        <InlineStack align="space-between">
          <Text as="h3" variant="headingSm" tone="subdued">
            {title}
          </Text>
          {icon}
        </InlineStack>
        <Text as="p" variant="heading2xl">
          {value}
        </Text>
        {change !== undefined && change !== null && (
          <InlineStack gap="100" align="start">
            {getTrendIcon()}
            <Text as="span" variant="bodySm" tone={getTrendColor()}>
              {change > 0 ? "+" : ""}
              {change}% vs last period
            </Text>
          </InlineStack>
        )}
        {change === null && (
          <Text as="span" variant="bodySm" tone="subdued">
            First period - no comparison available
          </Text>
        )}
      </BlockStack>
    </Card>
  );
}

export function KPICards({ data }: KPICardsProps) {
  const formatCurrencyAmount = (amount: number) => {
    return formatCurrency(amount, data.currency_code);
  };

  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  return (
    <BlockStack gap="400">
      <Text as="h2" variant="headingLg">
        Recommendation Performance
      </Text>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "16px",
        }}
      >
        <KPICard
          title="Total Revenue"
          value={formatCurrencyAmount(data.total_revenue)}
          change={data.revenue_change}
          trend={
            data.revenue_change !== null
              ? data.revenue_change >= 0
                ? "up"
                : "down"
              : "neutral"
          }
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
        />
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
        />
      </div>
    </BlockStack>
  );
}
