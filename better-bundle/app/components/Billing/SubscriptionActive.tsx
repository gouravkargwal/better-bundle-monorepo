import {
  Card,
  BlockStack,
  InlineStack,
  Text,
  Badge,
  ProgressBar,
  Icon,
  Divider,
} from "@shopify/polaris";
import { CheckCircleIcon } from "@shopify/polaris-icons";
import { BillingLayout } from "./BillingLayout";
import { HeroHeader } from "../UI/HeroHeader";
import { formatCurrency } from "app/utils/currency";

interface SubscriptionActiveProps {
  billingPlan: any;
}

export function SubscriptionActive({ billingPlan }: SubscriptionActiveProps) {
  // ✅ USE NEW DATA - Only post-trial revenue (industry standard)
  const metrics = billingPlan.currentCycleMetrics || {
    purchases: { count: 0, total: 0 },
    refunds: {
      count: 0,
      total: 0,
      same_period_total: 0,
      cross_period_total: 0,
    },
    net_revenue: 0, // Only post-trial revenue
    commission: 0,
    final_commission: 0,
    capped_amount: billingPlan.capped_amount || 1000,
    days_remaining: 0,
  };

  const usagePercentage =
    (metrics.final_commission / metrics.capped_amount) * 100;
  const isNearLimit = usagePercentage > 80;
  const isOverLimit = usagePercentage > 100;
  const remainingAmount = metrics.capped_amount - metrics.final_commission;

  return (
    <BillingLayout>
      <BlockStack gap="500">
        <HeroHeader
          badge="✅ Active"
          title="Subscription Active"
          subtitle="Your usage-based billing is active and Better Bundle services are running"
          gradient="green"
        />

        {/* Status Banner */}
        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="400">
              <div
                style={{
                  padding: "20px",
                  backgroundColor: "#F0FDF4",
                  borderRadius: "12px",
                  border: "1px solid #BBF7D0",
                }}
              >
                <BlockStack gap="300">
                  <InlineStack gap="300" align="start" blockAlign="center">
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        minWidth: "40px",
                        minHeight: "40px",
                        padding: "12px",
                        backgroundColor: "#22C55E15",
                        borderRadius: "16px",
                        border: "2px solid #22C55E30",
                      }}
                    >
                      <Icon source={CheckCircleIcon} tone="base" />
                    </div>
                    <BlockStack gap="100">
                      <div style={{ color: "#14532D" }}>
                        <Text as="h3" variant="headingMd" fontWeight="bold">
                          All Systems Running
                        </Text>
                      </div>
                      <Text as="p" variant="bodyMd" tone="subdued">
                        Your bundles are live and generating revenue. You're
                        only charged for sales made through Better Bundle.
                      </Text>
                    </BlockStack>
                    <Badge tone="success" size="large">
                      Active
                    </Badge>
                  </InlineStack>
                </BlockStack>
              </div>
            </BlockStack>
          </div>
        </Card>
        {/* ✅ IMPROVED: Usage Overview Card */}
        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="400">
              {/* Header with days remaining */}
              <InlineStack align="space-between" blockAlign="center">
                <div
                  style={{
                    padding: "16px",
                    backgroundColor: isOverLimit
                      ? "#FEF2F2"
                      : isNearLimit
                        ? "#FEF3C7"
                        : "#DBEAFE",
                    borderRadius: "12px",
                    border: `1px solid ${isOverLimit ? "#FECACA" : isNearLimit ? "#FCD34D" : "#BAE6FD"}`,
                    flex: 1,
                  }}
                >
                  <Text as="h3" variant="headingMd" fontWeight="bold">
                    📊 Current Billing Cycle
                  </Text>
                </div>
                {metrics.days_remaining > 0 && (
                  <Badge tone="info" size="large">
                    {metrics.days_remaining} days left
                  </Badge>
                )}
              </InlineStack>

              {/* ✅ NEW: Revenue & Commission Side by Side */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
                  gap: "16px",
                }}
              >
                {/* Attributed Revenue Card */}
                <div
                  style={{
                    padding: "20px",
                    backgroundColor: "#F0F9FF",
                    borderRadius: "12px",
                    border: "1px solid #BAE6FD",
                  }}
                >
                  <BlockStack gap="200">
                    <Text variant="bodySm" tone="subdued">
                      Attributed Revenue
                    </Text>
                    <Text variant="heading2xl" fontWeight="bold">
                      {formatCurrency(
                        metrics.net_revenue,
                        billingPlan.currency,
                      )}
                    </Text>
                    <BlockStack gap="100">
                      <InlineStack align="space-between">
                        <Text variant="bodySm" tone="subdued">
                          Sales:
                        </Text>
                        <Text variant="bodySm">
                          {formatCurrency(
                            metrics.purchases.total,
                            billingPlan.currency,
                          )}{" "}
                          ({metrics.purchases.count})
                        </Text>
                      </InlineStack>
                      {/* ✅ NO REFUND DISPLAY - Commission based on gross attributed revenue only */}
                    </BlockStack>
                  </BlockStack>
                </div>

                {/* ✅ NEW: Your Bill (Commission) */}
                <div
                  style={{
                    padding: "20px",
                    backgroundColor: "#ECFDF5",
                    borderRadius: "12px",
                    border: "2px solid #10B981",
                  }}
                >
                  <BlockStack gap="200">
                    <Text variant="bodySm" tone="subdued">
                      Your Current Bill
                    </Text>
                    <Text
                      variant="heading2xl"
                      fontWeight="bold"
                      tone={isOverLimit ? "critical" : undefined}
                    >
                      {formatCurrency(
                        metrics.final_commission,
                        billingPlan.currency,
                      )}
                    </Text>
                    <Text variant="bodySm" tone="subdued">
                      3% of{" "}
                      {formatCurrency(
                        metrics.net_revenue,
                        billingPlan.currency,
                      )}
                    </Text>
                    {isOverLimit && (
                      <div
                        style={{
                          padding: "8px",
                          backgroundColor: "#FEF2F2",
                          borderRadius: "6px",
                        }}
                      >
                        <Text variant="bodySm" tone="critical">
                          ⚠️ Capped at{" "}
                          {formatCurrency(
                            metrics.capped_amount,
                            billingPlan.currency,
                          )}
                        </Text>
                      </div>
                    )}
                  </BlockStack>
                </div>
              </div>

              {/* ✅ EXISTING: Progress Bar - Keep but update values */}
              <BlockStack gap="200">
                <ProgressBar
                  progress={Math.min(usagePercentage, 100)}
                  tone={
                    isOverLimit
                      ? "critical"
                      : isNearLimit
                        ? "warning"
                        : "success"
                  }
                  size="large"
                />
                <InlineStack align="space-between">
                  <Text variant="bodySm" fontWeight="semibold">
                    {usagePercentage.toFixed(1)}% of cap used
                  </Text>
                  <Text variant="bodySm" tone="subdued">
                    {formatCurrency(
                      metrics.final_commission,
                      billingPlan.currency,
                    )}{" "}
                    /{" "}
                    {formatCurrency(
                      metrics.capped_amount,
                      billingPlan.currency,
                    )}
                  </Text>
                </InlineStack>
              </BlockStack>

              {/* ✅ EXISTING: Warnings - Keep as is */}
              {isNearLimit && !isOverLimit && (
                <div
                  style={{
                    padding: "12px",
                    backgroundColor: "#FEF3C7",
                    borderRadius: "8px",
                    border: "1px solid #FCD34D",
                  }}
                >
                  <Text variant="bodySm">
                    ⚠️ You're approaching your spending cap.
                  </Text>
                </div>
              )}
            </BlockStack>
          </div>
        </Card>

        {/* ✅ Post-Trial Billing Info */}
        {metrics.purchases.count === 0 && (
          <Card>
            <div
              style={{
                padding: "20px",
                backgroundColor: "#F0F9FF",
                borderRadius: "12px",
                border: "1px solid #BAE6FD",
              }}
            >
              <BlockStack gap="300">
                <InlineStack gap="200" blockAlign="center">
                  <Text as="span" variant="heading2xl">
                    🎯
                  </Text>
                  <Text variant="headingMd" fontWeight="bold">
                    Fresh Start Billing
                  </Text>
                </InlineStack>

                <Text variant="bodyMd" tone="subdued">
                  Your billing cycle started fresh after trial completion.
                  You'll only be charged for new sales made through Better
                  Bundle.
                </Text>
              </BlockStack>
            </div>
          </Card>
        )}

        {/* ✅ NO REFUND DISPLAY - Commission based on gross attributed revenue only */}

        {/* Help Cards */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
            gap: "24px",
          }}
        >
          {/* Understanding Your Bill */}
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
                      📖 Understanding Your Bill
                    </Text>
                  </div>
                </div>
                <BlockStack gap="200">
                  <Text as="p" variant="bodySm">
                    <strong>Attributed Revenue:</strong> Total sales value from
                    orders containing your bundles
                  </Text>
                  <Text as="p" variant="bodySm">
                    <strong>Your Charge:</strong> 3% of attributed revenue, up
                    to your monthly cap
                  </Text>
                  <Text as="p" variant="bodySm">
                    <strong>The Cap:</strong> Maximum you'll pay per 30-day
                    billing cycle
                  </Text>
                  <Text as="p" variant="bodySm">
                    <strong>No Sales = $0:</strong> You only pay when bundles
                    generate revenue
                  </Text>
                </BlockStack>
              </BlockStack>
            </div>
          </Card>

          {/* Need to Adjust */}
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
                      💡 Need to Adjust?
                    </Text>
                  </div>
                </div>
                <BlockStack gap="200">
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Increase your cap:</strong> Cancel and set up a new
                    subscription with a higher monthly limit
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Decrease your cap:</strong> Cancel and create a new
                    subscription with a lower limit
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Cancel anytime:</strong> No long-term commitments or
                    cancellation fees
                  </Text>
                </BlockStack>
              </BlockStack>
            </div>
          </Card>
        </div>
      </BlockStack>
    </BillingLayout>
  );
}
