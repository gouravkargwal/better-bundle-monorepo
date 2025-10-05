import {
  Card,
  BlockStack,
  InlineStack,
  Text,
  Badge,
  ProgressBar,
} from "@shopify/polaris";
import { HeroHeader } from "../UI/HeroHeader";
import { BillingLayout } from "./BillingLayout";

interface TrialActiveProps {
  billingPlan: any;
  formatCurrency: (amount: number, currency?: string) => string;
}

export function TrialActive({ billingPlan, formatCurrency }: TrialActiveProps) {
  const trialProgress =
    (billingPlan.attributed_revenue / billingPlan.trial_threshold) * 100;
  const remainingAmount =
    billingPlan.trial_threshold - billingPlan.attributed_revenue;

  return (
    <BlockStack gap="500">
      <HeroHeader
        badge="🚀 Free Trial Active"
        title="Your Free Trial is Active!"
        subtitle="Use Better Bundle to drive sales and track your progress"
        gradient="blue"
      />

      <BillingLayout>
        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="400">
              <InlineStack align="space-between">
                <Text as="h2" variant="headingMd" fontWeight="bold">
                  Trial Progress
                </Text>
                <Badge tone="success">Active</Badge>
              </InlineStack>

              <div
                style={{
                  padding: "24px",
                  backgroundColor: "#F0FDF4",
                  borderRadius: "12px",
                  border: "1px solid #22C55E",
                  marginBottom: "16px",
                }}
              >
                <BlockStack gap="300">
                  <InlineStack gap="200" align="start">
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: "48px",
                        height: "48px",
                        backgroundColor: "#22C55E",
                        borderRadius: "50%",
                        color: "white",
                        fontSize: "24px",
                      }}
                    >
                      📊
                    </div>
                    <BlockStack gap="100">
                      <Text as="p" variant="bodyMd" fontWeight="bold">
                        {billingPlan.usage_count} orders tracked
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Revenue:{" "}
                        {formatCurrency(
                          billingPlan.attributed_revenue,
                          billingPlan.currency,
                        )}
                      </Text>
                    </BlockStack>
                  </InlineStack>

                  {/* Progress Bar */}
                  <BlockStack gap="200">
                    <InlineStack align="space-between">
                      <Text as="p" variant="bodySm">
                        Trial Progress:{" "}
                        {formatCurrency(
                          billingPlan.attributed_revenue,
                          billingPlan.currency,
                        )}
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Goal:{" "}
                        {formatCurrency(
                          billingPlan.trial_threshold,
                          billingPlan.currency,
                        )}
                      </Text>
                    </InlineStack>

                    <ProgressBar
                      progress={Math.min(trialProgress, 100)}
                      tone={trialProgress > 80 ? "critical" : "success"}
                    />

                    <Text as="p" variant="bodySm" tone="subdued">
                      {trialProgress >= 100
                        ? "Trial threshold reached! Setup billing to continue."
                        : `${formatCurrency(remainingAmount, billingPlan.currency)} remaining to reach threshold`}
                    </Text>
                  </BlockStack>
                </BlockStack>
              </div>

              <div
                style={{
                  padding: "24px",
                  backgroundColor: "#F0F9FF",
                  borderRadius: "12px",
                  border: "1px solid #BAE6FD",
                }}
              >
                <BlockStack gap="200">
                  <Text as="p" variant="bodyMd" fontWeight="bold">
                    💡 What happens next?
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    When you reach{" "}
                    {formatCurrency(
                      billingPlan.trial_threshold,
                      billingPlan.currency,
                    )}{" "}
                    in attributed revenue, we'll prompt you to set up billing.
                    You'll then pay 3% of attributed revenue.
                  </Text>
                </BlockStack>
              </div>
            </BlockStack>
          </div>
        </Card>
      </BillingLayout>
    </BlockStack>
  );
}
