import {
  Card,
  BlockStack,
  InlineStack,
  Text,
  Badge,
  ProgressBar,
  Button,
  Modal,
  RangeSlider,
} from "@shopify/polaris";
import { BillingLayout } from "./BillingLayout";
import { HeroHeader } from "../UI/HeroHeader";
import { formatCurrency } from "app/utils/currency";
import { useState } from "react";
import { useBillingActions } from "../../hooks/useBillingActions";

interface SubscriptionActiveProps {
  billingPlan: any;
  shopCurrency: string;
}

export function SubscriptionActive({
  billingPlan,
  shopCurrency,
}: SubscriptionActiveProps) {
  // ✅ USE NEW DATA - Only post-trial revenue (industry standard)
  const metrics = billingPlan.currentCycleMetrics || {
    purchases: { count: 0, total: 0 },

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

  const [showCapIncreaseModal, setShowCapIncreaseModal] = useState(false);
  const [newCapAmount, setNewCapAmount] = useState(0);
  const { handleIncreaseCap, isLoading } = useBillingActions(shopCurrency);

  const handleCapIncrease = async () => {
    if (newCapAmount <= metrics.capped_amount) {
      alert("New cap must be higher than current cap");
      return;
    }

    const result = await handleIncreaseCap(newCapAmount);
    if (result.success) {
      setShowCapIncreaseModal(false);
      alert("Cap increased successfully! Services will resume.");
    } else {
      alert(`Failed to increase cap: ${result.error}`);
    }
  };

  return (
    <BillingLayout>
      <BlockStack gap="500">
        <HeroHeader
          badge="✅ Active"
          title="Subscription Active"
          subtitle="Your usage-based billing is active and Better Bundle services are running"
          gradient="green"
        />

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
                    {`${metrics.days_remaining} days left`}
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
                    <InlineStack align="space-between" blockAlign="center">
                      <Text as="span" variant="bodySm" tone="subdued">
                        Attributed Revenue
                      </Text>
                      <Text as="span" variant="bodySm" tone="subdued">
                        📈 Revenue Generated
                      </Text>
                    </InlineStack>
                    <Text as="h3" variant="heading2xl" fontWeight="bold">
                      {formatCurrency(metrics.net_revenue, shopCurrency)}
                    </Text>
                    <BlockStack gap="100">
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm" tone="subdued">
                          Sales:
                        </Text>
                        <Text as="span" variant="bodySm">
                          {formatCurrency(
                            metrics.purchases.total,
                            shopCurrency,
                          )}{" "}
                          ({metrics.purchases.count})
                        </Text>
                      </InlineStack>
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm" tone="subdued">
                          Max Revenue:
                        </Text>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {formatCurrency(
                            metrics.capped_amount / 0.03,
                            shopCurrency,
                          )}{" "}
                          (before cap)
                        </Text>
                      </InlineStack>
                    </BlockStack>
                  </BlockStack>
                </div>

                {/* ✅ ENHANCED: Your Bill (Commission) */}
                <div
                  style={{
                    padding: "20px",
                    backgroundColor: isOverLimit
                      ? "#FEF2F2"
                      : isNearLimit
                        ? "#FEF3C7"
                        : "#ECFDF5",
                    borderRadius: "12px",
                    border: `2px solid ${
                      isOverLimit
                        ? "#EF4444"
                        : isNearLimit
                          ? "#F59E0B"
                          : "#10B981"
                    }`,
                  }}
                >
                  <BlockStack gap="200">
                    <InlineStack align="space-between" blockAlign="center">
                      <Text as="span" variant="bodySm" tone="subdued">
                        Your Current Bill
                      </Text>
                      <Text as="span" variant="bodySm" tone="subdued">
                        💰 {usagePercentage.toFixed(1)}% of cap
                      </Text>
                    </InlineStack>
                    <Text
                      as="h3"
                      variant="heading2xl"
                      fontWeight="bold"
                      tone={isOverLimit ? "critical" : undefined}
                    >
                      {formatCurrency(metrics.final_commission, shopCurrency)}
                    </Text>
                    <Text as="span" variant="bodySm" tone="subdued">
                      3% of {formatCurrency(metrics.net_revenue, shopCurrency)}
                    </Text>
                    <BlockStack gap="100">
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm" tone="subdued">
                          Remaining Cap:
                        </Text>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {formatCurrency(
                            Math.max(
                              0,
                              metrics.capped_amount - metrics.final_commission,
                            ),
                            shopCurrency,
                          )}
                        </Text>
                      </InlineStack>
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm" tone="subdued">
                          Reset in:
                        </Text>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {metrics.days_remaining} days
                        </Text>
                      </InlineStack>
                    </BlockStack>
                    {isOverLimit && (
                      <div
                        style={{
                          padding: "8px",
                          backgroundColor: "#FEF2F2",
                          borderRadius: "6px",
                        }}
                      >
                        <Text as="span" variant="bodySm" tone="critical">
                          ⚠️ Capped at{" "}
                          {formatCurrency(metrics.capped_amount, shopCurrency)}
                        </Text>
                      </div>
                    )}
                  </BlockStack>
                </div>
              </div>

              {/* ✅ NEW: Dual Progress Bars */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
                  gap: "24px",
                }}
              >
                {/* Revenue Progress Bar */}
                <BlockStack gap="200">
                  <div
                    style={{
                      padding: "16px",
                      backgroundColor: "#F0FDF4",
                      borderRadius: "12px",
                      border: "1px solid #BBF7D0",
                    }}
                  >
                    <BlockStack gap="200">
                      <InlineStack align="space-between" blockAlign="center">
                        <Text
                          as="span"
                          variant="bodySm"
                          fontWeight="semibold"
                          tone="subdued"
                        >
                          📈 Revenue vs Cap
                        </Text>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {Math.round(
                            (metrics.net_revenue /
                              (metrics.capped_amount / 0.03)) *
                              100,
                          )}
                          % of max
                        </Text>
                      </InlineStack>
                      <ProgressBar
                        progress={Math.min(
                          (metrics.net_revenue /
                            (metrics.capped_amount / 0.03)) *
                            100,
                          100,
                        )}
                        tone="success"
                        size="large"
                      />
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm" fontWeight="semibold">
                          {formatCurrency(metrics.net_revenue, shopCurrency)}
                        </Text>
                        <Text as="span" variant="bodySm" tone="subdued">
                          /{" "}
                          {formatCurrency(
                            metrics.capped_amount / 0.03,
                            shopCurrency,
                          )}{" "}
                          max
                        </Text>
                      </InlineStack>
                    </BlockStack>
                  </div>
                </BlockStack>

                {/* Commission Cap Progress Bar */}
                <BlockStack gap="200">
                  <div
                    style={{
                      padding: "16px",
                      backgroundColor: isOverLimit
                        ? "#FEF2F2"
                        : isNearLimit
                          ? "#FEF3C7"
                          : "#F0F9FF",
                      borderRadius: "12px",
                      border: `1px solid ${
                        isOverLimit
                          ? "#FECACA"
                          : isNearLimit
                            ? "#FCD34D"
                            : "#BAE6FD"
                      }`,
                    }}
                  >
                    <BlockStack gap="200">
                      <InlineStack align="space-between" blockAlign="center">
                        <Text
                          as="span"
                          variant="bodySm"
                          fontWeight="semibold"
                          tone="subdued"
                        >
                          💰 Commission Cap
                        </Text>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {usagePercentage.toFixed(1)}% used
                        </Text>
                      </InlineStack>
                      <ProgressBar
                        progress={Math.min(usagePercentage, 100)}
                        tone={isOverLimit ? "critical" : "success"}
                        size="large"
                      />
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm" fontWeight="semibold">
                          {formatCurrency(
                            metrics.final_commission,
                            shopCurrency,
                          )}
                        </Text>
                        <Text as="span" variant="bodySm" tone="subdued">
                          /{" "}
                          {formatCurrency(metrics.capped_amount, shopCurrency)}
                        </Text>
                      </InlineStack>
                    </BlockStack>
                  </div>
                </BlockStack>
              </div>

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
                  <Text as="span" variant="bodySm">
                    ⚠️ You're approaching your spending cap.
                  </Text>
                </div>
              )}

              {/* ✅ NEW: Capped State Warning */}
              {isOverLimit && (
                <div
                  style={{
                    padding: "16px",
                    backgroundColor: "#FEF2F2",
                    borderRadius: "12px",
                    border: "1px solid #FECACA",
                  }}
                >
                  <BlockStack gap="200">
                    <InlineStack gap="200" align="start" blockAlign="center">
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          minWidth: "32px",
                          minHeight: "32px",
                          padding: "8px",
                          backgroundColor: "#EF444415",
                          borderRadius: "12px",
                          border: "2px solid #EF444430",
                        }}
                      >
                        <Text as="span" variant="headingMd">
                          🚫
                        </Text>
                      </div>
                      <BlockStack gap="100">
                        <div style={{ color: "#DC2626" }}>
                          <Text as="h4" variant="headingMd" fontWeight="bold">
                            Monthly Cap Reached
                          </Text>
                        </div>
                        <Text as="span" variant="bodySm" tone="subdued">
                          You've reached your monthly spending cap of{" "}
                          {formatCurrency(metrics.capped_amount, shopCurrency)}.
                          New commissions will be tracked but not charged until
                          next billing cycle.
                        </Text>
                      </BlockStack>
                    </InlineStack>

                    <div
                      style={{
                        padding: "12px",
                        backgroundColor: "#FEF3C7",
                        borderRadius: "8px",
                        border: "1px solid #FCD34D",
                      }}
                    >
                      <BlockStack gap="200">
                        <Text as="p" variant="bodySm">
                          💡 Your billing cycle resets in{" "}
                          {metrics.days_remaining} days. You can also increase
                          your monthly cap anytime.
                        </Text>
                        <Button
                          variant="primary"
                          size="slim"
                          onClick={() => {
                            setNewCapAmount(metrics.capped_amount * 1.5); // 50% increase as default
                            setShowCapIncreaseModal(true);
                          }}
                        >
                          Increase Monthly Cap
                        </Button>
                      </BlockStack>
                    </div>
                  </BlockStack>
                </div>
              )}
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

      {/* Cap Increase Modal */}
      <Modal
        open={showCapIncreaseModal}
        onClose={() => setShowCapIncreaseModal(false)}
        title="Increase Monthly Cap"
        primaryAction={{
          content: "Increase Cap",
          onAction: handleCapIncrease,
          loading: isLoading,
        }}
        secondaryActions={[
          {
            content: "Cancel",
            onAction: () => setShowCapIncreaseModal(false),
          },
        ]}
      >
        <Modal.Section>
          <BlockStack gap="400">
            <Text as="p" variant="bodyMd">
              Increase your monthly spending cap to continue using Better Bundle
              services.
            </Text>

            <div>
              <Text as="p" variant="bodySm" tone="subdued">
                Current Cap:{" "}
                {formatCurrency(metrics.capped_amount, shopCurrency)}
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                New Cap: {formatCurrency(newCapAmount, shopCurrency)}
              </Text>
            </div>

            <RangeSlider
              label="New Monthly Cap"
              min={metrics.capped_amount * 1.1} // 10% higher than current
              max={metrics.capped_amount * 5} // 5x current cap
              step={50}
              value={newCapAmount}
              onChange={(value) =>
                setNewCapAmount(typeof value === "number" ? value : value[0])
              }
              output
            />

            <div
              style={{
                padding: "12px",
                backgroundColor: "#F0F9FF",
                borderRadius: "8px",
                border: "1px solid #BAE6FD",
              }}
            >
              <Text as="p" variant="bodySm">
                💡 Services will resume immediately after cap increase.
              </Text>
            </div>
          </BlockStack>
        </Modal.Section>
      </Modal>
    </BillingLayout>
  );
}
