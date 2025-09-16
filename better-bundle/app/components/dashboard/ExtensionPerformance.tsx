import {
  Card,
  Text,
  BlockStack,
  DataTable,
  Badge,
  InlineStack,
} from "@shopify/polaris";
import type { ExtensionPerformanceData } from "../../services/dashboard.service";
import { formatCurrency } from "../../utils/currency";

interface ExtensionPerformanceProps {
  data: ExtensionPerformanceData[];
}

export function ExtensionPerformance({ data }: ExtensionPerformanceProps) {
  const formatCurrencyAmount = (amount: number, currencyCode: string) => {
    return formatCurrency(amount, currencyCode);
  };

  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  const getExtensionDisplayName = (extensionType: string) => {
    switch (extensionType) {
      case "venus":
        return "Venus (Customer Account)";
      case "phoenix":
        return "Phoenix (Checkout)";
      case "apollo":
        return "Apollo (Post-Purchase)";
      case "atlas":
        return "Atlas (Web Pixels)";
      default:
        return extensionType;
    }
  };

  const getExtensionBadge = (extensionType: string) => {
    const colors = {
      venus: "success",
      phoenix: "info",
      apollo: "warning",
      atlas: "attention",
    } as const;

    return (
      <Badge tone={colors[extensionType as keyof typeof colors] || "info"}>
        {getExtensionDisplayName(extensionType)}
      </Badge>
    );
  };

  const getPerformanceBadge = (conversionRate: number) => {
    if (conversionRate >= 15) {
      return <Badge tone="success">High</Badge>;
    } else if (conversionRate >= 10) {
      return <Badge tone="info">Medium</Badge>;
    } else {
      return <Badge tone="warning">Low</Badge>;
    }
  };

  const rows = data.map((extension) => [
    getExtensionBadge(extension.extension_type),
    formatCurrencyAmount(extension.revenue, extension.currency_code),
    formatPercentage(extension.conversion_rate),
    extension.customers.toLocaleString(),
    getPerformanceBadge(extension.conversion_rate),
  ]);

  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack align="space-between">
          <BlockStack gap="200">
            <Text as="h2" variant="headingLg">
              Extension Performance
            </Text>
            <Text as="p" variant="bodyMd" tone="subdued">
              See which extensions drive the most value for your store
            </Text>
          </BlockStack>
        </InlineStack>
        <DataTable
          columnContentTypes={["text", "text", "text", "text", "text"]}
          headings={[
            "Extension",
            "Revenue",
            "Conversion Rate",
            "Customers",
            "Performance",
          ]}
          rows={rows}
          footerContent={`Showing data for ${data.length} extensions`}
        />
      </BlockStack>
    </Card>
  );
}
