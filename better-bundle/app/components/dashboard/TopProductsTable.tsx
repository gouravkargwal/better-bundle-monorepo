import {
  Card,
  Text,
  BlockStack,
  DataTable,
  Badge,
  InlineStack,
  Button,
} from "@shopify/polaris";
import type { TopProductData } from "../../services/dashboard.service";
import { formatCurrency } from "../../utils/currency";

interface TopProductsTableProps {
  data: TopProductData[];
}

export function TopProductsTable({ data }: TopProductsTableProps) {
  const formatCurrencyAmount = (amount: number, currencyCode: string) => {
    return formatCurrency(amount, currencyCode);
  };

  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`;
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

  const rows = data.map((product, index) => [
    `#${index + 1}`,
    product.title,
    formatCurrencyAmount(product.revenue, product.currency_code),
    formatPercentage(product.conversion_rate),
    product.clicks.toLocaleString(),
    product.recommendations_shown.toLocaleString(),
    getPerformanceBadge(product.conversion_rate),
  ]);

  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack align="space-between">
          <BlockStack gap="200">
            <Text as="h2" variant="headingLg">
              Top Performing Products
            </Text>
            <Text as="p" variant="bodyMd" tone="subdued">
              Products with the highest recommendation performance
            </Text>
          </BlockStack>
          <Button variant="plain" size="slim">
            View All
          </Button>
        </InlineStack>
        <DataTable
          columnContentTypes={[
            "text",
            "text",
            "text",
            "text",
            "text",
            "text",
            "text",
          ]}
          headings={[
            "Rank",
            "Product",
            "Revenue",
            "Conv. Rate",
            "Clicks",
            "Shown",
            "Performance",
          ]}
          rows={rows}
          footerContent={`Showing top ${data.length} products`}
        />
      </BlockStack>
    </Card>
  );
}
