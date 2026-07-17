import { Card, BlockStack, InlineStack, Text, Badge } from "@shopify/polaris";
import type { SubscriptionData } from "../types/billing.types";

interface SubscriptionActiveProps {
  subscriptionData: SubscriptionData;
  shopCurrency: string;
}

export function SubscriptionActive({
  subscriptionData,
  shopCurrency,
}: SubscriptionActiveProps) {
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: shopCurrency,
    }).format(amount);
  };

  return (
    <BlockStack gap="500">
      <Card>
        <BlockStack gap="300">
          <InlineStack align="space-between" blockAlign="center">
            <BlockStack gap="100">
              <Text variant="headingMd" as="h3">
                ✅ Subscription Active
              </Text>
              <Text as="p" tone="subdued">
                Your BetterBundle subscription is active and services are
                running.
              </Text>
            </BlockStack>
            <Badge tone="success" size="large">
              Active
            </Badge>
          </InlineStack>
        </BlockStack>
      </Card>

      <Card>
        <div style={{ padding: "24px" }}>
          <BlockStack gap="200">
            <InlineStack align="space-between">
              <Text as="span" variant="bodyMd" tone="subdued">
                Monthly Plan
              </Text>
              <Text as="span" variant="bodyMd" fontWeight="bold">
                {formatCurrency(subscriptionData.monthlyPrice)}/mo
              </Text>
            </InlineStack>
            <Text as="p" variant="bodySm" tone="subdued">
              Billed automatically every 30 days. Cancel anytime — no
              long-term commitment.
            </Text>
          </BlockStack>
        </div>
      </Card>
    </BlockStack>
  );
}
