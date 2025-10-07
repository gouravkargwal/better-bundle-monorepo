import {
  Card,
  BlockStack,
  InlineStack,
  Text,
  Badge,
  ProgressBar,
  Button,
  Icon,
} from "@shopify/polaris";
import { CheckCircleIcon, StarIcon } from "@shopify/polaris-icons";
import { HeroHeader } from "../UI/HeroHeader";
import { BillingLayout } from "./BillingLayout";
import { formatCurrency } from "app/utils/currency";

interface TrialActiveProps {
  shopCurrency: string;
  trialPlanData: any;
}

export function TrialActive({ shopCurrency, trialPlanData }: TrialActiveProps) {
  const trialProgress =
    (trialPlanData.attributedRevenue / trialPlanData.trialThreshold) * 100;
  const remainingAmount =
    trialPlanData.trialThreshold - trialPlanData.attributedRevenue;
  const isNearThreshold = trialProgress >= 80;
  const hasReachedThreshold = trialProgress >= 100;

  return (
    <BlockStack gap="500">
      <HeroHeader
        badge="🚀 Free Trial Active"
        title="Your Free Trial is Active!"
        subtitle="Drive sales with Better Bundle - completely free until you reach your threshold"
        gradient="blue"
      />

      <BillingLayout>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "2fr 1fr",
            gap: "var(--p-space-400)",
          }}
        >
          {/* Main Progress Card */}
          <Card>
            <BlockStack gap="400">
              {/* Header */}
              <InlineStack align="space-between" blockAlign="center">
                <Text as="h2" variant="headingMd" fontWeight="semibold">
                  Trial Progress
                </Text>
                <Badge tone="success" icon={CheckCircleIcon}>
                  Active
                </Badge>
              </InlineStack>

              {/* Progress Section */}
              <div
                style={{
                  padding: "20px",
                  backgroundColor: hasReachedThreshold ? "#FEF3C7" : "#F0FDF4",
                  borderRadius: "12px",
                  border: `2px solid ${hasReachedThreshold ? "#F59E0B" : "#22C55E"}`,
                }}
              >
                <BlockStack gap="400">
                  {/* Revenue Stats */}
                  <InlineStack align="space-between" blockAlign="end">
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySm" tone="subdued">
                        Attributed Revenue
                      </Text>
                      <Text as="h3" variant="headingLg" fontWeight="bold">
                        {formatCurrency(
                          trialPlanData.attributedRevenue,
                          shopCurrency,
                        )}
                      </Text>
                    </BlockStack>
                    <BlockStack gap="100" align="end">
                      <Text as="p" variant="bodySm" tone="subdued">
                        Trial Threshold
                      </Text>
                      <Text as="p" variant="headingMd" fontWeight="semibold">
                        {formatCurrency(
                          trialPlanData.trialThreshold,
                          shopCurrency,
                        )}
                      </Text>
                    </BlockStack>
                  </InlineStack>

                  {/* Progress Bar */}
                  <BlockStack gap="200">
                    <ProgressBar
                      progress={Math.min(trialProgress, 100)}
                      tone={hasReachedThreshold ? "primary" : "success"}
                      size="medium"
                    />
                    <InlineStack align="space-between">
                      <Text as="p" variant="bodySm" fontWeight="medium">
                        {Math.min(trialProgress, 100).toFixed(1)}% Complete
                      </Text>
                      {!hasReachedThreshold && (
                        <Text as="p" variant="bodySm" tone="subdued">
                          {formatCurrency(remainingAmount, shopCurrency)} to go
                        </Text>
                      )}
                    </InlineStack>
                  </BlockStack>

                  {/* Status Message */}
                  {hasReachedThreshold ? (
                    <div
                      style={{
                        padding: "12px",
                        backgroundColor: "white",
                        borderRadius: "8px",
                      }}
                    >
                      <InlineStack gap="200" blockAlign="center">
                        <div style={{ color: "#F59E0B" }}>
                          <Icon source={StarIcon} tone="warning" />
                        </div>
                        <BlockStack gap="100">
                          <Text as="p" variant="bodyMd" fontWeight="semibold">
                            Congratulations! You've reached your trial threshold
                          </Text>
                          <Text as="p" variant="bodySm" tone="subdued">
                            Ready to continue? Set up billing to keep using
                            Better Bundle
                          </Text>
                        </BlockStack>
                      </InlineStack>
                    </div>
                  ) : isNearThreshold ? (
                    <InlineStack gap="200" blockAlign="center">
                      <Text as="p" variant="bodySm" tone="subdued">
                        You're almost there! Approaching your trial threshold
                      </Text>
                    </InlineStack>
                  ) : null}
                </BlockStack>
              </div>

              {/* CTA Button for threshold reached */}
              {hasReachedThreshold && (
                <Button variant="primary" size="large" fullWidth>
                  Set Up Billing to Continue
                </Button>
              )}
            </BlockStack>
          </Card>

          {/* What's Next Card */}
          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd" fontWeight="semibold">
                💡 What's Next?
              </Text>
              <BlockStack gap="200">
                <div style={{ display: "flex", gap: "8px" }}>
                  <Text as="span">1.</Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Continue using all features completely free
                  </Text>
                </div>
                <div style={{ display: "flex", gap: "8px" }}>
                  <Text as="span">2.</Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    When you reach{" "}
                    {formatCurrency(trialPlanData.trialThreshold, shopCurrency)}
                    , set up billing
                  </Text>
                </div>
                <div style={{ display: "flex", gap: "8px" }}>
                  <Text as="span">3.</Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Pay only 3% of attributed revenue - only when you make sales
                  </Text>
                </div>
              </BlockStack>
            </BlockStack>
          </Card>
        </div>
      </BillingLayout>
    </BlockStack>
  );
}
