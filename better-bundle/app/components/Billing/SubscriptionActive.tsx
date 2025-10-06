import {
  Card,
  BlockStack,
  InlineStack,
  Text,
  Badge,
  ProgressBar,
  Icon,
} from "@shopify/polaris";
import { CheckCircleIcon, CalendarIcon } from "@shopify/polaris-icons";
import { BillingLayout } from "./BillingLayout";
import { HeroHeader } from "../UI/HeroHeader";
import { formatCurrency } from "app/utils/currency";

interface SubscriptionActiveProps {
  billingPlan: any;
}

export function SubscriptionActive({ billingPlan }: SubscriptionActiveProps) {
  const usagePercentage =
    (billingPlan.attributed_revenue / billingPlan.capped_amount) * 100;
  const remainingAmount =
    billingPlan.capped_amount - billingPlan.attributed_revenue;
  const isNearLimit = usagePercentage > 80;
  const isOverLimit = usagePercentage > 100;

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

        {/* Usage Overview Card */}
        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="400">
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
                }}
              >
                <div
                  style={{
                    color: isOverLimit
                      ? "#991B1B"
                      : isNearLimit
                        ? "#92400E"
                        : "#0C4A6E",
                  }}
                >
                  <Text as="h3" variant="headingMd" fontWeight="bold">
                    📊 Current Billing Cycle Usage
                  </Text>
                </div>
              </div>

              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="center">
                  <BlockStack gap="100">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Attributed Revenue This Cycle
                    </Text>
                    <Text as="h2" variant="headingLg" fontWeight="bold">
                      {formatCurrency(
                        billingPlan.attributed_revenue,
                        billingPlan.currency,
                      )}
                    </Text>
                  </BlockStack>
                  <BlockStack gap="100">
                    <Text
                      as="p"
                      variant="bodySm"
                      tone="subdued"
                      alignment="end"
                    >
                      Monthly Cap
                    </Text>
                    <Text
                      as="p"
                      variant="headingMd"
                      fontWeight="semibold"
                      alignment="end"
                    >
                      {formatCurrency(
                        billingPlan.capped_amount,
                        billingPlan.currency,
                      )}
                    </Text>
                  </BlockStack>
                </InlineStack>

                <BlockStack gap="200">
                  <ProgressBar
                    progress={Math.min(usagePercentage, 100)}
                    tone={
                      isOverLimit
                        ? "critical"
                        : isNearLimit
                          ? "critical"
                          : "success"
                    }
                    size="large"
                  />

                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm" fontWeight="semibold">
                      {usagePercentage.toFixed(1)}% of cap used
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      {isOverLimit
                        ? `Over limit by ${formatCurrency(billingPlan.attributed_revenue - billingPlan.capped_amount, billingPlan.currency)}`
                        : `${formatCurrency(remainingAmount, billingPlan.currency)} remaining`}
                    </Text>
                  </InlineStack>
                </BlockStack>

                {isNearLimit && !isOverLimit && (
                  <div
                    style={{
                      padding: "12px",
                      backgroundColor: "#FEF3C7",
                      borderRadius: "8px",
                      border: "1px solid #FCD34D",
                    }}
                  >
                    <Text as="p" variant="bodySm" tone="subdued">
                      ⚠️ You're approaching your spending cap. Consider
                      increasing it if your bundles are performing well.
                    </Text>
                  </div>
                )}

                {isOverLimit && (
                  <div
                    style={{
                      padding: "12px",
                      backgroundColor: "#FEF2F2",
                      borderRadius: "8px",
                      border: "1px solid #FECACA",
                    }}
                  >
                    <Text as="p" variant="bodySm" tone="subdued">
                      🔴 You've reached your spending cap. Services continue
                      normally, but you may want to increase your cap for next
                      cycle.
                    </Text>
                  </div>
                )}
              </BlockStack>
            </BlockStack>
          </div>
        </Card>

        {/* Billing Details Card */}
        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="400">
              <div
                style={{
                  padding: "16px",
                  backgroundColor: "#F8FAFC",
                  borderRadius: "12px",
                  border: "1px solid #E2E8F0",
                }}
              >
                <Text as="h3" variant="headingMd" fontWeight="bold">
                  💳 Billing Details
                </Text>
              </div>

              <div
                style={{
                  padding: "20px",
                  backgroundColor: "#FFFFFF",
                  borderRadius: "8px",
                  border: "1px solid #E2E8F0",
                }}
              >
                <BlockStack gap="200">
                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Billing Rate:
                    </Text>
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      3% of attributed revenue
                    </Text>
                  </InlineStack>

                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Monthly Spending Cap:
                    </Text>
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      {formatCurrency(
                        billingPlan.capped_amount,
                        billingPlan.currency,
                      )}
                    </Text>
                  </InlineStack>

                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Billing Cycle:
                    </Text>
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      Every 30 Days
                    </Text>
                  </InlineStack>

                  <div
                    style={{
                      height: "1px",
                      backgroundColor: "#E2E8F0",
                      margin: "8px 0",
                    }}
                  />

                  <InlineStack align="space-between" blockAlign="center">
                    <InlineStack gap="200" blockAlign="center">
                      <Icon source={CalendarIcon} tone="base" />
                      <Text as="p" variant="bodySm" tone="subdued">
                        Next Billing Date:
                      </Text>
                    </InlineStack>
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      {new Date(
                        Date.now() + 30 * 24 * 60 * 60 * 1000,
                      ).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </Text>
                  </InlineStack>
                </BlockStack>
              </div>

              <div
                style={{
                  padding: "12px",
                  backgroundColor: "#DBEAFE",
                  borderRadius: "8px",
                  border: "1px solid #BAE6FD",
                }}
              >
                <Text as="p" variant="bodySm" tone="subdued">
                  💡 Your actual charge will be 3% of{" "}
                  {formatCurrency(
                    billingPlan.attributed_revenue,
                    billingPlan.currency,
                  )}{" "}
                  ={" "}
                  {formatCurrency(
                    billingPlan.attributed_revenue * 0.03,
                    billingPlan.currency,
                  )}{" "}
                  for this cycle (unless it exceeds your cap).
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
