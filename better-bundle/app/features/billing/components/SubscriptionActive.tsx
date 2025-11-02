import { useState } from "react";
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
  onIncreaseCap,
}: SubscriptionActiveProps) {
  const [showCapIncreaseModal, setShowCapIncreaseModal] = useState(false);
  const [newCapAmount, setNewCapAmount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: shopCurrency,
    }).format(amount);
  };

  const usagePercentage = subscriptionData.usagePercentage;
  const isNearCap = usagePercentage > 80;
  const isAtCap = usagePercentage >= 100;

  const handleCapIncrease = async () => {
    if (newCapAmount <= subscriptionData.spendingLimit) {
      alert("New cap must be higher than current cap");
      return;
    }

    setIsLoading(true);
    try {
      const result = await onIncreaseCap(newCapAmount);
      if (result.success) {
        setShowCapIncreaseModal(false);
        alert("Cap increased successfully! Services will resume.");
      } else {
        alert(`Failed to increase cap: ${result.error}`);
      }
    } catch (error) {
      alert("An unexpected error occurred");
    } finally {
      setIsLoading(false);
    }
  };

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
                  Your usage-based billing is active and Better Bundle services
                  are running
                </Text>
              </BlockStack>
              <Badge tone="success" size="large">
                Active
              </Badge>
            </InlineStack>
          </BlockStack>
        </Card>

        {/* Usage Overview Card */}
        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="400">
              {/* Header with status */}
              <InlineStack align="space-between" blockAlign="center">
                <div
                  style={{
                    padding: "16px",
                    backgroundColor: isAtCap
                      ? "#FEF2F2"
                      : isNearCap
                        ? "#FEF3C7"
                        : "#DBEAFE",
                    borderRadius: "12px",
                    border: `1px solid ${isAtCap ? "#FECACA" : isNearCap ? "#FCD34D" : "#BAE6FD"}`,
                    flex: 1,
                  }}
                >
                  <Text as="h3" variant="headingMd" fontWeight="bold">
                    📊 Current Billing Cycle
                  </Text>
                </div>
              </InlineStack>

              {/* Revenue & Commission Side by Side */}
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
                      {formatCurrency(subscriptionData.currentUsage / 0.03)}
                    </Text>
                    <BlockStack gap="100">
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm" tone="subdued">
                          Revenue Limit (at cap):
                        </Text>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {formatCurrency(
                            subscriptionData.spendingLimit / 0.03,
                          )}
                        </Text>
                      </InlineStack>
                    </BlockStack>
                  </BlockStack>
                </div>

                {/* Your Bill (Commission) */}
                <div
                  style={{
                    padding: "20px",
                    backgroundColor: isAtCap
                      ? "#FEF2F2"
                      : isNearCap
                        ? "#FEF3C7"
                        : "#ECFDF5",
                    borderRadius: "12px",
                    border: `2px solid ${
                      isAtCap ? "#EF4444" : isNearCap ? "#F59E0B" : "#10B981"
                    }`,
                  }}
                >
                  <BlockStack gap="200">
                    <InlineStack align="space-between" blockAlign="center">
                      <Text as="span" variant="bodySm" tone="subdued">
                        Your Current Bill
                      </Text>
                      <Text as="span" variant="bodySm" tone="subdued">
                        💰 {Number(usagePercentage.toFixed(1))}% of cap
                      </Text>
                    </InlineStack>
                    <Text
                      as="h3"
                      variant="heading2xl"
                      fontWeight="bold"
                      tone={isAtCap ? "critical" : undefined}
                    >
                      {formatCurrency(subscriptionData.currentUsage)}
                    </Text>

                    {/* ✅ Smart Breakdown: Show only when relevant */}
                    {subscriptionData.expectedCharge > 0 ||
                    (subscriptionData.rejectedAmount &&
                      subscriptionData.rejectedAmount > 0) ? (
                      <div
                        style={{
                          padding: "12px",
                          backgroundColor: "#F0F9FF",
                          borderRadius: "8px",
                          border: "1px solid #BAE6FD",
                        }}
                      >
                        <BlockStack gap="100">
                          <Text
                            as="span"
                            variant="bodySm"
                            fontWeight="semibold"
                            tone="subdued"
                          >
                            💳 Charge Breakdown
                          </Text>
                          <InlineStack align="space-between">
                            <Text as="span" variant="bodySm" tone="subdued">
                              ✓ Recorded:
                            </Text>
                            <Text
                              as="span"
                              variant="bodySm"
                              fontWeight="medium"
                            >
                              {formatCurrency(
                                subscriptionData.shopifyUsage || 0,
                              )}
                            </Text>
                          </InlineStack>
                          {subscriptionData.expectedCharge > 0 && (
                            <InlineStack align="space-between">
                              <Text as="span" variant="bodySm" tone="subdued">
                                ⏳ Pending:
                              </Text>
                              <Text
                                as="span"
                                variant="bodySm"
                                fontWeight="medium"
                              >
                                {formatCurrency(
                                  subscriptionData.expectedCharge,
                                )}
                              </Text>
                            </InlineStack>
                          )}
                          {subscriptionData.rejectedAmount &&
                            subscriptionData.rejectedAmount > 0 && (
                              <InlineStack align="space-between">
                                <Text as="span" variant="bodySm" tone="subdued">
                                  🚫 Rejected:
                                </Text>
                                <Text
                                  as="span"
                                  variant="bodySm"
                                  fontWeight="medium"
                                  tone="critical"
                                >
                                  {formatCurrency(
                                    subscriptionData.rejectedAmount,
                                  )}
                                </Text>
                              </InlineStack>
                            )}
                        </BlockStack>
                      </div>
                    ) : (
                      <Text as="span" variant="bodySm" tone="subdued">
                        ✓ All{" "}
                        {formatCurrency(
                          subscriptionData.shopifyUsage ||
                            subscriptionData.currentUsage,
                        )}{" "}
                        recorded to Shopify
                      </Text>
                    )}

                    <Text as="span" variant="bodySm" tone="subdued">
                      3% commission on{" "}
                      {formatCurrency(subscriptionData.currentUsage / 0.03)}{" "}
                      revenue
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
                              subscriptionData.spendingLimit -
                                subscriptionData.currentUsage,
                            ),
                          )}
                        </Text>
                      </InlineStack>
                    </BlockStack>
                    {isAtCap && (
                      <div
                        style={{
                          padding: "8px",
                          backgroundColor: "#FEF2F2",
                          borderRadius: "6px",
                        }}
                      >
                        <Text as="span" variant="bodySm" tone="critical">
                          ⚠️ Capped at{" "}
                          {formatCurrency(subscriptionData.spendingLimit)}
                        </Text>
                      </div>
                    )}
                  </BlockStack>
                </div>
              </div>

              {/* Dual Progress Bars */}
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
                          {Number(
                            (
                              (subscriptionData.currentUsage /
                                0.03 /
                                (subscriptionData.spendingLimit / 0.03)) *
                              100
                            ).toFixed(1),
                          )}
                          % of max
                        </Text>
                      </InlineStack>
                      <ProgressBar
                        progress={Number(
                          Math.min(
                            (subscriptionData.currentUsage /
                              subscriptionData.spendingLimit) *
                              100,
                            100,
                          ).toFixed(1),
                        )}
                        tone="success"
                        size="large"
                      />
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm" fontWeight="semibold">
                          {formatCurrency(subscriptionData.currentUsage / 0.03)}
                        </Text>
                        <Text as="span" variant="bodySm" tone="subdued">
                          /{" "}
                          {formatCurrency(
                            subscriptionData.spendingLimit / 0.03,
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
                      backgroundColor: isAtCap
                        ? "#FEF2F2"
                        : isNearCap
                          ? "#FEF3C7"
                          : "#F0F9FF",
                      borderRadius: "12px",
                      border: `1px solid ${
                        isAtCap ? "#FECACA" : isNearCap ? "#FCD34D" : "#BAE6FD"
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
                          {Number(usagePercentage.toFixed(1))}% used
                        </Text>
                      </InlineStack>
                      <ProgressBar
                        progress={Number(
                          Math.min(usagePercentage, 100).toFixed(1),
                        )}
                        tone={isAtCap ? "critical" : "success"}
                        size="large"
                      />
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm" fontWeight="semibold">
                          {formatCurrency(subscriptionData.currentUsage)}
                        </Text>
                        <Text as="span" variant="bodySm" tone="subdued">
                          / {formatCurrency(subscriptionData.spendingLimit)}
                        </Text>
                      </InlineStack>
                    </BlockStack>
                  </div>
                </BlockStack>
              </div>

              {/* Warnings */}
              {isNearCap && !isAtCap && (
                <Banner tone="info">
                  <Text as="p">
                    You're approaching your monthly spending cap (
                    {subscriptionData.usagePercentage}% used).
                  </Text>
                </Banner>
              )}

              {/* Capped State Warning */}
              {isAtCap && (
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
                          {formatCurrency(subscriptionData.spendingLimit)}. New
                          commissions will be tracked but not charged until next
                          billing cycle.
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
                          💡 Your billing cycle resets in 30 days. You can also
                          increase your monthly cap anytime.
                        </Text>
                        <Button
                          variant="primary"
                          size="slim"
                          onClick={() => {
                            setNewCapAmount(
                              subscriptionData.spendingLimit * 1.5,
                            ); // 50% increase as default
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
                Current Cap: {formatCurrency(subscriptionData.spendingLimit)}
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                New Cap: {formatCurrency(newCapAmount)}
              </Text>
            </div>

            <RangeSlider
              label="New Monthly Cap"
              min={subscriptionData.spendingLimit * 1.1} // 10% higher than current
              max={subscriptionData.spendingLimit * 5} // 5x current cap
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
    </>
  );
}
