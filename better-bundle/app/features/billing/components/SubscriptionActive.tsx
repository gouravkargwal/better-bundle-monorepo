import {
  Box, Card, BlockStack, InlineStack, Text, Badge
} from "@shopify/polaris";
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

  const ratePercent = (subscriptionData.commissionRate * 100)
    .toFixed(1)
    .replace(/\.0$/, "");

  const billingCycle = subscriptionData.billingCycle;
  const nextBillingDate = billingCycle?.endDate
    ? new Date(billingCycle.endDate)
    : null;
  const daysUntilNextBilling = nextBillingDate
    ? Math.max(
        0,
        Math.ceil(
          (nextBillingDate.getTime() - Date.now()) / (1000 * 60 * 60 * 24),
        ),
      )
    : null;

  return (
    <>
      <BlockStack gap="500">
        {/* Status Header */}
        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between" blockAlign="center">
              <BlockStack gap="100">
                <Text variant="headingMd" as="h3">
                  ✅ Subscription Active
                </Text>
                <Text as="p" tone="subdued">
                  Better Bundle is running. You are billed only on the revenue
                  it generates.
                </Text>
              </BlockStack>
              <Badge tone="success" size="large">
                Active
              </Badge>
            </InlineStack>
          </BlockStack>
        </Card>

        {/* Plan Overview Card */}
        <Card>
          <BlockStack gap="400">
            {/* Header with status */}
            <InlineStack align="space-between" blockAlign="center">
              <Box padding="400" background="bg-surface-info" borderRadius="300">
                <Text as="span">
                  <Text as="h3" variant="headingMd" fontWeight="bold">
                    💡 Pay As You Go Pricing
                  </Text>
                </Text>
              </Box>
            </InlineStack>

            {/* Plan Details Side by Side */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
                gap: "16px",
              }}
            >
              {/* Plan Card */}
              <Box padding="500" background="bg-surface-info" borderRadius="300">
                <BlockStack gap="200">
                  <InlineStack align="space-between" blockAlign="center">
                    <Text as="span" variant="bodySm" tone="subdued">
                      Plan
                    </Text>
                    <Text as="span" variant="bodySm" tone="subdued">
                      🏷️ {subscriptionData.planName}
                    </Text>
                  </InlineStack>
                  <Text as="h3" variant="heading2xl" fontWeight="bold">
                    {formatCurrency(subscriptionData.usageThisCycle)}
                  </Text>
                  <Text as="span" variant="bodySm" tone="subdued">
                    this cycle · {ratePercent}% of{" "}
                    {formatCurrency(subscriptionData.attributedThisCycle)}{" "}
                    attributed · capped at{" "}
                    {formatCurrency(subscriptionData.cappedAmount)}
                  </Text>
                </BlockStack>
              </Box>

              {/* Billing Cycle Card */}
              <Box padding="500" background="bg-surface-success" borderRadius="300">
                <BlockStack gap="200">
                  <InlineStack align="space-between" blockAlign="center">
                    <Text as="span" variant="bodySm" tone="subdued">
                      Next Billing
                    </Text>
                    <Text as="span" variant="bodySm" tone="subdued">
                      📅 Billing Cycle
                    </Text>
                  </InlineStack>
                  {daysUntilNextBilling !== null ? (
                    <>
                      <Text as="h3" variant="heading2xl" fontWeight="bold">
                        {daysUntilNextBilling > 0
                          ? `${daysUntilNextBilling} days`
                          : "Today"}
                      </Text>
                      <Text as="span" variant="bodySm" tone="subdued">
                        {nextBillingDate
                          ? nextBillingDate.toLocaleDateString("en-US", {
                              month: "long",
                              day: "numeric",
                              year: "numeric",
                            })
                          : "N/A"}
                      </Text>
                    </>
                  ) : (
                    <>
                      <Text as="h3" variant="heading2xl" fontWeight="bold">
                        —
                      </Text>
                      <Text as="span" variant="bodySm" tone="subdued">
                        Billing cycle info unavailable
                      </Text>
                    </>
                  )}
                </BlockStack>
              </Box>
            </div>

            {/* Plan Benefits */}
            <Box padding="400" background="bg-surface-success" borderRadius="300">
              <BlockStack gap="200">
                <Text
                  as="span"
                  variant="bodySm"
                  fontWeight="semibold"
                  tone="success"
                >
                  ✓ What's Included
                </Text>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "repeat(auto-fit, minmax(200px, 1fr))",
                    gap: "8px",
                  }}
                >
                  <InlineStack gap="200">
                    <Text as="span" variant="bodySm" tone="success">
                      ✓
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      AI-powered recommendations
                    </Text>
                  </InlineStack>
                  <InlineStack gap="200">
                    <Text as="span" variant="bodySm" tone="success">
                      ✓
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Attribution & analytics
                    </Text>
                  </InlineStack>
                  <InlineStack gap="200">
                    <Text as="span" variant="bodySm" tone="success">
                      ✓
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Priority support
                    </Text>
                  </InlineStack>
                </div>
              </BlockStack>
            </Box>

            {/* Info Banner */}
            <Box padding="400" background="bg-surface-warning" borderRadius="300">
              <Text as="p" variant="bodySm" tone="subdued">
                💡 You are charged {ratePercent}% of the revenue we
                attribute to our recommendations, never more than{" "}
                {formatCurrency(subscriptionData.cappedAmount)} in a 30-day cycle.
                A month we generate nothing costs you nothing.
              </Text>
            </Box>
          </BlockStack>

        </Card>

        {/* Help Cards */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
            gap: "24px",
          }}
        >
          {/* Understanding Your Plan */}
          <Card>
            <div style={{ padding: "20px" }}>
              <BlockStack gap="300">
                <Box padding="400" background="bg-surface-info" borderRadius="300">
                  <Text as="span">
                    <Text as="h3" variant="headingMd" fontWeight="bold">
                      📖 Managing Your Subscription
                    </Text>
                  </Text>
                </Box>
                <BlockStack gap="200">
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Plan Changes:</strong> Cancel at any time. You are
                    only ever billed for revenue already generated.
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Billing:</strong> {ratePercent}% of the revenue we
                    attribute to our recommendations, charged as it accrues and
                    never more than{" "}
                    {formatCurrency(subscriptionData.cappedAmount)} in a 30-day
                    cycle.
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Invoices:</strong> View all past invoices and
                    billing history in the billing section.
                  </Text>
                </BlockStack>
              </BlockStack>
            </div>
          </Card>

          {/* Contact Support */}
          <Card>
            <div style={{ padding: "20px" }}>
              <BlockStack gap="300">
                <Box padding="400" background="bg-surface-warning" borderRadius="300">
                  <Text as="span" tone="caution">
                    <Text as="h3" variant="headingMd" fontWeight="bold">
                      💡 Need Help?
                    </Text>
                  </Text>
                </Box>
                <BlockStack gap="200">
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Questions about your plan?</strong> Contact our
                    support team for assistance with billing, upgrades, or
                    feature requests.
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Need to cancel?</strong> Visit the billing settings
                    to cancel your subscription. No cancellation fees.
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Payment issues?</strong> We'll notify you if there's
                    a problem with your payment method.
                  </Text>
                </BlockStack>
              </BlockStack>
            </div>
          </Card>
        </div>
      </BlockStack>
    </>
  );
}
