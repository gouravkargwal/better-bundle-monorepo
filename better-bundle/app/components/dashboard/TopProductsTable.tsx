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

  // Handle empty data
  if (!data || data.length === 0) {
    return (
      <BlockStack gap="500">
        <div
          style={{
            padding: "24px",
            backgroundColor: "#FEF3C7",
            borderRadius: "12px",
            border: "1px solid #FCD34D",
          }}
        >
          <div style={{ color: "#92400E" }}>
            <Text as="h2" variant="headingLg" fontWeight="bold">
              🏆 Top Performing Products
            </Text>
          </div>
          <div style={{ marginTop: "8px" }}>
            <Text as="p" variant="bodyMd" tone="subdued">
              Products with the highest recommendation performance
            </Text>
          </div>
        </div>

        <div
          style={{
            padding: "48px",
            textAlign: "center",
            backgroundColor: "#F8FAFC",
            borderRadius: "16px",
            border: "1px solid #E2E8F0",
          }}
        >
          <div style={{ fontSize: "48px", marginBottom: "16px" }}>📦</div>
          <Text as="h3" variant="headingMd" fontWeight="bold">
            No products yet
          </Text>
          <div style={{ marginTop: "8px" }}>
            <Text as="p" variant="bodyMd" tone="subdued">
              Start getting recommendations to see your top performing products
              here
            </Text>
          </div>
        </div>
      </BlockStack>
    );
  }

  const rows = data.map((product, index) => [
    `#${index + 1}`,
    product.title,
    formatCurrencyAmount(product.revenue, product.currency_code),
    formatPercentage(product.conversion_rate),
    product.clicks.toLocaleString(),
    product.recommendations_shown.toLocaleString(),
    product.customers.toLocaleString(),
    getPerformanceBadge(product.conversion_rate),
  ]);

  return (
    <BlockStack gap="500">
      <div
        style={{
          padding: "24px",
          backgroundColor: "#FEF3C7",
          borderRadius: "12px",
          border: "1px solid #FCD34D",
        }}
      >
        <div style={{ color: "#92400E" }}>
          <Text as="h2" variant="headingLg" fontWeight="bold">
            🏆 Top Performing Products
          </Text>
        </div>
        <div style={{ marginTop: "8px" }}>
          <Text as="p" variant="bodyMd" tone="subdued">
            Products with the highest recommendation performance
          </Text>
        </div>
      </div>

      <Card>
        <BlockStack gap="400">
          <InlineStack align="space-between">
            <BlockStack gap="200">
              <Text as="h3" variant="headingMd" fontWeight="medium">
                Performance Rankings
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                Ranked by conversion rate and revenue
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
              "text",
            ]}
            headings={[
              "Rank",
              "Product",
              "Revenue",
              "Conv. Rate",
              "Clicks",
              "Shown",
              "Customers",
              "Performance",
            ]}
            rows={rows}
            footerContent={`Showing top ${data.length} products`}
          />
        </BlockStack>
      </Card>
    </BlockStack>
  );
}
