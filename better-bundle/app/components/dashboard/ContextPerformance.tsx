import { Card, Text, BlockStack, DataTable, Badge } from "@shopify/polaris";
import type { ContextPerformanceData } from "../../services/dashboard.service";
import { formatCurrency } from "../../utils/currency";

interface ContextPerformanceProps {
  data: ContextPerformanceData[];
}

export function ContextPerformance({ data }: ContextPerformanceProps) {
  const formatCurrencyAmount = (amount: number, currencyCode: string) => {
    return formatCurrency(amount, currencyCode);
  };

  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  const getContextDisplayName = (context: string) => {
    switch (context) {
      case "profile":
        return "Profile Page";
      case "order_status":
        return "Order Status";
      case "order_history":
        return "Order History";
      default:
        return context;
    }
  };

  const getContextBadge = (context: string) => {
    const colors = {
      profile: "success",
      order_status: "info",
      order_history: "warning",
    } as const;

    return (
      <Badge tone={colors[context as keyof typeof colors] || "info"}>
        {getContextDisplayName(context)}
      </Badge>
    );
  };

  const rows = data.map((item) => [
    getContextBadge(item.context),
    formatCurrencyAmount(item.revenue, item.currency_code),
    formatPercentage(item.conversion_rate),
    item.clicks.toLocaleString(),
    item.recommendations_shown.toLocaleString(),
  ]);

  return (
    <Card>
      <BlockStack gap="400">
        <Text as="h2" variant="headingLg">
          Performance by Context
        </Text>
        <Text as="p" variant="bodyMd" tone="subdued">
          See how your recommendations perform across different pages
        </Text>
        <DataTable
          columnContentTypes={["text", "text", "text", "text", "text"]}
          headings={[
            "Context",
            "Revenue",
            "Conversion Rate",
            "Clicks",
            "Recommendations Shown",
          ]}
          rows={rows}
          footerContent={`Showing data for ${data.length} contexts`}
        />
      </BlockStack>
    </Card>
  );
}
