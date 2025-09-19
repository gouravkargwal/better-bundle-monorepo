import {
  Card,
  Text,
  BlockStack,
  InlineStack,
  Badge,
  Icon,
  Box,
} from "@shopify/polaris";
import {
  ArrowDownIcon,
  ReceiptIcon,
  AlertTriangleIcon,
} from "@shopify/polaris-icons";
import { formatCurrency } from "../../utils/currency";

interface RefundAttributionData {
  total_refunds: number;
  attributed_refunds: number;
  refund_rate: number;
  attributed_refund_rate: number;
  currency_code: string;
  period: string;
}

interface RefundAttributionProps {
  data: RefundAttributionData;
}

export function RefundAttribution({ data }: RefundAttributionProps) {
  const formatCurrencyAmount = (amount: number) =>
    formatCurrency(amount, data.currency_code);

  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  const getRefundRateColor = (rate: number) => {
    if (rate < 5) return "success";
    if (rate < 10) return "warning";
    return "critical";
  };

  return (
    <Card>
      <BlockStack gap="400">
        <Text as="h2" variant="headingLg">
          Refund Attribution
        </Text>
        <Text as="p" variant="bodyMd" tone="subdued">
          Refunds from orders influenced by your extensions
        </Text>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "16px",
          }}
        >
          {/* Total Refunds */}
          <Box padding="400" background="bg-surface-secondary">
            <BlockStack gap="200">
              <InlineStack gap="200" align="space-between">
                <Text as="h3" variant="headingSm">
                  Total Refunds
                </Text>
                <Icon source={ReceiptIcon} tone="base" />
              </InlineStack>
              <Text as="p" variant="headingLg">
                {formatCurrencyAmount(data.total_refunds)}
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                All refunds in {data.period}
              </Text>
            </BlockStack>
          </Box>

          {/* Attributed Refunds */}
          <Box padding="400" background="bg-surface-secondary">
            <BlockStack gap="200">
              <InlineStack gap="200" align="space-between">
                <Text as="h3" variant="headingSm">
                  Attributed Refunds
                </Text>
                <Icon source={ArrowDownIcon} tone="base" />
              </InlineStack>
              <Text as="p" variant="headingLg">
                {formatCurrencyAmount(data.attributed_refunds)}
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                From extension-influenced orders
              </Text>
            </BlockStack>
          </Box>

          {/* Refund Rate */}
          <Box padding="400" background="bg-surface-secondary">
            <BlockStack gap="200">
              <InlineStack gap="200" align="space-between">
                <Text as="h3" variant="headingSm">
                  Overall Refund Rate
                </Text>
                <Badge tone={getRefundRateColor(data.refund_rate)} size="small">
                  {formatPercentage(data.refund_rate)}
                </Badge>
              </InlineStack>
              <Text as="p" variant="bodySm" tone="subdued">
                Total refund rate
              </Text>
            </BlockStack>
          </Box>

          {/* Attributed Refund Rate */}
          <Box padding="400" background="bg-surface-secondary">
            <BlockStack gap="200">
              <InlineStack gap="200" align="space-between">
                <Text as="h3" variant="headingSm">
                  Extension Refund Rate
                </Text>
                <Badge
                  tone={getRefundRateColor(data.attributed_refund_rate)}
                  size="small"
                >
                  {formatPercentage(data.attributed_refund_rate)}
                </Badge>
              </InlineStack>
              <Text as="p" variant="bodySm" tone="subdued">
                From attributed orders
              </Text>
            </BlockStack>
          </Box>
        </div>

        {/* Insight */}
        {data.attributed_refund_rate > data.refund_rate && (
          <Box padding="300" background="bg-surface-warning-subdued">
            <InlineStack gap="200" align="start">
              <Icon source={AlertTriangleIcon} tone="warning" />
              <BlockStack gap="100">
                <Text as="p" variant="bodySm" tone="warning">
                  Extension-influenced orders have a higher refund rate
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  Consider reviewing recommendation quality and targeting
                </Text>
              </BlockStack>
            </InlineStack>
          </Box>
        )}
      </BlockStack>
    </Card>
  );
}
