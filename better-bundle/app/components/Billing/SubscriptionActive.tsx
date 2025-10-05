import { Card, BlockStack, InlineStack, Text, Badge, Button, ProgressBar } from "@shopify/polaris";
import { BillingLayout } from "./BillingLayout";

interface SubscriptionActiveProps {
  billingPlan: any;
  formatCurrency: (amount: number, currency?: string) => string;
  handleCancelSubscription: () => void;
  isLoading: boolean;
}

export function SubscriptionActive({
  billingPlan,
  formatCurrency,
  handleCancelSubscription,
  isLoading,
}: SubscriptionActiveProps) {
  const usagePercentage = (billingPlan.attributed_revenue / billingPlan.capped_amount) * 100;
  const remainingAmount = billingPlan.capped_amount - billingPlan.attributed_revenue;

  return (
    <BillingLayout>
      <Card>
        <div style={{ padding: "24px" }}>
          <BlockStack gap="400">
            <InlineStack align="space-between">
              <Text as="h2" variant="headingMd" fontWeight="bold">
                Active Subscription
              </Text>
              <Badge tone="success">Active</Badge>
            </InlineStack>

            {/* Usage Overview */}
            <div
              style={{
                padding: "24px",
                backgroundColor: "#F0FDF4",
                borderRadius: "12px",
                border: "1px solid #22C55E",
              }}
            >
              <BlockStack gap="300">
                <Text as="p" variant="bodyMd" fontWeight="bold">
                  📊 Current Usage
                </Text>
                
                <BlockStack gap="200">
                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm">
                      Revenue: {formatCurrency(billingPlan.attributed_revenue, billingPlan.currency)}
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Cap: {formatCurrency(billingPlan.capped_amount, billingPlan.currency)}
                    </Text>
                  </InlineStack>
                  
                  <ProgressBar
                    progress={Math.min(usagePercentage, 100)}
                    tone={usagePercentage > 80 ? "critical" : usagePercentage > 60 ? "warning" : "success"}
                  />
                  
                  <Text as="p" variant="bodySm" tone="subdued">
                    {usagePercentage > 100 
                      ? `Over limit by ${formatCurrency(billingPlan.attributed_revenue - billingPlan.capped_amount, billingPlan.currency)}`
                      : `${formatCurrency(remainingAmount, billingPlan.currency)} remaining this month`
                    }
                  </Text>
                </BlockStack>
              </BlockStack>
            </div>

            {/* Billing Details */}
            <div
              style={{
                padding: "24px",
                backgroundColor: "#F8FAFC",
                borderRadius: "12px",
                border: "1px solid #E2E8F0",
              }}
            >
              <BlockStack gap="300">
                <Text as="p" variant="bodyMd" fontWeight="bold">
                  💳 Billing Details
                </Text>
                
                <BlockStack gap="200">
                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm">Rate:</Text>
                    <Text as="p" variant="bodySm" fontWeight="bold">3% of attributed revenue</Text>
                  </InlineStack>
                  
                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm">Monthly Cap:</Text>
                    <Text as="p" variant="bodySm" fontWeight="bold">
                      {formatCurrency(billingPlan.capped_amount, billingPlan.currency)}
                    </Text>
                  </InlineStack>
                  
                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm">Next Billing:</Text>
                    <Text as="p" variant="bodySm" fontWeight="bold">
                      {new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toLocaleDateString()}
                    </Text>
                  </InlineStack>
                </BlockStack>
              </BlockStack>
            </div>

            {/* Actions */}
            <InlineStack gap="200" align="center">
              <Button
                variant="secondary"
                tone="critical"
                onClick={handleCancelSubscription}
                loading={isLoading}
              >
                Cancel Subscription
              </Button>
              <Button
                variant="tertiary"
                onClick={() => window.open('/admin/apps/better-bundle/billing/history', '_blank')}
              >
                View Billing History
              </Button>
            </InlineStack>
          </BlockStack>
        </div>
      </Card>
    </BillingLayout>
  );
}
