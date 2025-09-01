import { Card, BlockStack, Text, InlineStack, Badge } from "@shopify/polaris";

interface PricingPlanProps {
  showDetails?: boolean;
  compact?: boolean;
}

export default function PricingPlan({
  showDetails = true,
  compact = false,
}: PricingPlanProps) {
  return (
    <Card>
      <BlockStack gap="400">
        <Text as="h3" variant="headingMd">
          📋 Performance-Based Pricing
        </Text>

        <BlockStack gap="300">
          <InlineStack align="space-between">
            <Text as="p" variant="bodyMd">
              <strong>Free Trial:</strong> 14 days
            </Text>
            <Badge tone="success">Active</Badge>
          </InlineStack>

          <Text as="p" variant="bodyMd">
            <strong>Base Commission:</strong> 1.5% of attributed revenue
          </Text>

          {showDetails && (
            <>
              <Text as="p" variant="bodyMd">
                <strong>Performance Bonuses:</strong>
              </Text>
              <BlockStack gap="200">
                <Text as="p" variant="bodySm" tone="subdued">
                  • Silver (5-10% conversion): +0.5% bonus
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  • Gold (10-15% conversion): +1.0% bonus
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  • Platinum (15%+ conversion): +1.5% bonus
                </Text>
              </BlockStack>
            </>
          )}

          <Text as="p" variant="bodyMd">
            <strong>What's Included:</strong> AI bundle analysis, smart
            recommendations, conversion tracking, and customer insights
          </Text>

          {!compact && (
            <Text as="p" variant="bodySm" tone="subdued">
              You only pay when you succeed. No upfront costs, just a small
              percentage of the additional revenue we help you generate.
            </Text>
          )}
        </BlockStack>
      </BlockStack>
    </Card>
  );
}
