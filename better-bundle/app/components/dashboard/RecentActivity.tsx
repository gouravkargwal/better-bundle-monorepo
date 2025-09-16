import {
  Card,
  Text,
  BlockStack,
  InlineStack,
  Badge,
  Divider,
} from "@shopify/polaris";
import type { RecentActivityData } from "../../services/dashboard.service";
import { formatCurrency } from "../../utils/currency";

interface RecentActivityProps {
  data: RecentActivityData;
}

interface ActivityItemProps {
  period: string;
  recommendations: number;
  clicks: number;
  revenue: number;
  customers: number;
  currencyCode: string;
  isHighlighted?: boolean;
}

function ActivityItem({
  period,
  recommendations,
  clicks,
  revenue,
  customers,
  currencyCode,
  isHighlighted,
}: ActivityItemProps) {
  const formatCurrencyAmount = (amount: number) => {
    return formatCurrency(amount, currencyCode);
  };

  const conversionRate =
    recommendations > 0 ? (clicks / recommendations) * 100 : 0;

  return (
    <BlockStack gap="200">
      <InlineStack align="space-between">
        <Text
          as="h3"
          variant="headingSm"
          tone={isHighlighted ? "base" : "subdued"}
        >
          {period}
        </Text>
        {isHighlighted && <Badge tone="info">Today</Badge>}
      </InlineStack>
      <InlineStack gap="400" wrap={false}>
        <BlockStack gap="100">
          <Text as="span" variant="bodySm" tone="subdued">
            Recommendations
          </Text>
          <Text as="span" variant="bodyMd" fontWeight="bold">
            {recommendations.toLocaleString()}
          </Text>
        </BlockStack>
        <BlockStack gap="100">
          <Text as="span" variant="bodySm" tone="subdued">
            Clicks
          </Text>
          <Text as="span" variant="bodyMd" fontWeight="bold">
            {clicks.toLocaleString()}
          </Text>
        </BlockStack>
        <BlockStack gap="100">
          <Text as="span" variant="bodySm" tone="subdued">
            Revenue
          </Text>
          <Text as="span" variant="bodyMd" fontWeight="bold">
            {formatCurrencyAmount(revenue)}
          </Text>
        </BlockStack>
        <BlockStack gap="100">
          <Text as="span" variant="bodySm" tone="subdued">
            Customers
          </Text>
          <Text as="span" variant="bodyMd" fontWeight="bold">
            {customers.toLocaleString()}
          </Text>
        </BlockStack>
        <BlockStack gap="100">
          <Text as="span" variant="bodySm" tone="subdued">
            Conv. Rate
          </Text>
          <Text as="span" variant="bodyMd" fontWeight="bold">
            {conversionRate.toFixed(1)}%
          </Text>
        </BlockStack>
      </InlineStack>
    </BlockStack>
  );
}

export function RecentActivity({ data }: RecentActivityProps) {
  return (
    <Card>
      <BlockStack gap="400">
        <Text as="h2" variant="headingLg">
          Recent Activity
        </Text>
        <Text as="p" variant="bodyMd" tone="subdued">
          Performance over the last few days
        </Text>

        <BlockStack gap="300">
          <ActivityItem
            period="Today"
            recommendations={data.today.recommendations}
            clicks={data.today.clicks}
            revenue={data.today.revenue}
            customers={data.today.customers}
            currencyCode={data.currency_code}
            isHighlighted={true}
          />

          <Divider />

          <ActivityItem
            period="Yesterday"
            recommendations={data.yesterday.recommendations}
            clicks={data.yesterday.clicks}
            revenue={data.yesterday.revenue}
            customers={data.yesterday.customers}
            currencyCode={data.currency_code}
          />

          <Divider />

          <ActivityItem
            period="This Week"
            recommendations={data.this_week.recommendations}
            clicks={data.this_week.clicks}
            revenue={data.this_week.revenue}
            customers={data.this_week.customers}
            currencyCode={data.currency_code}
          />
        </BlockStack>
      </BlockStack>
    </Card>
  );
}
