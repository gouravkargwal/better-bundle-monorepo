import { useState } from "react";
import {
  Card,
  BlockStack,
  InlineStack,
  Text,
  Badge,
  Button,
  Banner,
} from "@shopify/polaris";
import type { SubscriptionData } from "../types/billing.types";

interface SubscriptionActiveProps {
  subscriptionData: SubscriptionData;
  shopCurrency: string;
  onIncreaseCap: (
    newLimit: number,
  ) => Promise<{ success: boolean; error?: string }>;
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
                  Your flat-rate subscription is active and Better Bundle
                  services are running
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
          <div style={{ padding: "24px" }}>
            <BlockStack gap="400">
              {/* Header with status */}
              <InlineStack align="space-between" blockAlign="center">
                <div
                  style={{
                    padding: "16px",
                    backgroundColor: "#DBEAFE",
                    borderRadius: "12px",
                    border: "1px solid #BAE6FD",
                    flex: 1,
                  }}
                >
                  <Text as="h3" variant="headingMd" fontWeight="bold">
                    📊 Current Plan
                  </Text>
                </div>
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
                <div
                  style={{
                    padding: "20px",
                    backgroundColor: "#F0F9FF",
                    borderRadius: "12px",
                    border: "1px solid #BAE6FD",
                  }}
                >
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
                      {formatCurrency(subscriptionData.monthlyFee)}
                    </Text>
                    <Text as="span" variant="bodySm" tone="subdued">
                      per month, billed every 30 days
                    </Text>
                  </BlockStack>
                </div>

                {/* Billing Cycle Card */}
                <div
                  style={{
                    padding: "20px",
                    backgroundColor: "#ECFDF5",
                    borderRadius: "12px",
                    border: "1px solid #BBF7D0",
                  }}
                >
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
                </div>
              </div>

              {/* Plan Benefits */}
              <div
                style={{
                  padding: "16px",
                  backgroundColor: "#F0FDF4",
                  borderRadius: "12px",
                  border: "1px solid #BBF7D0",
                }}
              >
                <BlockStack gap="200">
                  <Text
                    as="span"
                    variant="bodySm"
                    fontWeight="semibold"
                    color="text-success"
                  >
                    ✓ What's Included
                  </Text>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                      gap: "8px",
                    }}
                  >
                    <InlineStack gap="200">
                      <Text as="span" variant="bodySm" color="text-success">
                        ✓
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        AI-powered recommendations
                      </Text>
                    </InlineStack>
                    <InlineStack gap="200">
                      <Text as="span" variant="bodySm" color="text-success">
                        ✓
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Attribution & analytics
                      </Text>
                    </InlineStack>
                    <InlineStack gap="200">
                      <Text as="span" variant="bodySm" color="text-success">
                        ✓
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Priority support
                      </Text>
                    </InlineStack>
                  </div>
                </BlockStack>
              </div>

              {/* Info Banner */}
              <div
                style={{
                  padding: "12px",
                  backgroundColor: "#FEF3C7",
                  borderRadius: "8px",
                  border: "1px solid #FCD34D",
                }}
              >
                <Text as="p" variant="bodySm" tone="subdued">
                  💡 Your flat-rate plan gives you full access to all features.
                  No usage tracking, no surprise charges — just one predictable
                  monthly fee.
                </Text>
              </div>
            </BlockStack>
          </div>
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
                <div
                  style={{
                    padding: "16px",
                    backgroundColor: "#DBEAFE",
                    borderRadius: "12px",
                    border: "1px solid #BAE6FD",
                  }}
                >
                  <div style={{ color: "#0C4A6E" }}>
                    <Text as="h3" variant="headingMd" fontWeight="bold">
                      📖 Managing Your Subscription
                    </Text>
                  </div>
                </div>
                <BlockStack gap="200">
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Plan Changes:</strong> Upgrade, downgrade, or cancel
                    your subscription at any time. Changes apply at the next billing
                    cycle.
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Billing:</strong> You'll be charged{" "}
                    {formatCurrency(subscriptionData.monthlyFee)} every 30 days.
                    No overage fees or usage tracking.
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Invoices:</strong> View all past invoices and billing
                    history in the billing section.
                  </Text>
                </BlockStack>
              </BlockStack>
            </div>
          </Card>

          {/* Contact Support */}
          <Card>
            <div style={{ padding: "20px" }}>
              <BlockStack gap="300">
                <div
                  style={{
                    padding: "16px",
                    backgroundColor: "#FEF3C7",
                    borderRadius: "12px",
                    border: "1px solid #FCD34D",
                  }}
                >
                  <div style={{ color: "#92400E" }}>
                    <Text as="h3" variant="headingMd" fontWeight="bold">
                      💡 Need Help?
                    </Text>
                  </div>
                </div>
                <BlockStack gap="200">
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Questions about your plan?</strong> Contact our support
                    team for assistance with billing, upgrades, or feature requests.
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Need to cancel?</strong> Visit the billing settings to
                    cancel your subscription. No cancellation fees.
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Payment issues?</strong> We'll notify you if there's a
                    problem with your payment method.
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
