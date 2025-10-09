import { useState } from "react";
import {
  BlockStack,
  Button,
  Card,
  InlineStack,
  Text,
  Icon,
  TextField,
  Banner,
  Badge,
} from "@shopify/polaris";
import { AlertTriangleIcon, CreditCardIcon } from "@shopify/polaris-icons";
import type { TrialData, BillingSetupData } from "../types/billing.types";

interface TrialCompletedProps {
  trialData: TrialData;
  shopCurrency: string;
  onSetupBilling: (
    setupData: BillingSetupData,
  ) => Promise<{ success: boolean; error?: string }>;
}

export function TrialCompleted({
  trialData,
  shopCurrency,
  onSetupBilling,
}: TrialCompletedProps) {
  const [spendingLimit, setSpendingLimit] = useState<string>("1000");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: shopCurrency,
    }).format(amount);
  };

  const handleSetupBilling = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const setupData: BillingSetupData = {
        spendingLimit: parseFloat(spendingLimit),
        currency: shopCurrency,
      };

      const result = await onSetupBilling(setupData);
      if (!result.success) {
        setError(result.error || "Failed to setup billing");
      }
    } catch (err) {
      setError("An unexpected error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  const currentValue = parseFloat(spendingLimit);
  const displayValue = Number.isFinite(currentValue) ? currentValue : 1000;
  const revenueCapacity = Math.round(displayValue / 0.03);

  return (
    <BlockStack gap="500">
      {/* Status Header */}
      <Card>
        <BlockStack gap="300">
          <InlineStack align="space-between" blockAlign="center">
            <BlockStack gap="100">
              <Text variant="headingMd" as="h3">
                💳 Action Required
              </Text>
              <Text as="p" tone="subdued">
                Your free trial has ended. Choose your spending limit and
                activate usage-based billing.
              </Text>
            </BlockStack>
            <Badge tone="warning" size="large">
              Action Required
            </Badge>
          </InlineStack>
        </BlockStack>
      </Card>

      <Card>
        <div style={{ padding: "24px" }}>
          <BlockStack gap="400">
            {/* Status Banner */}
            <div
              style={{
                padding: "20px",
                backgroundColor: "#FEF3C7",
                borderRadius: "12px",
                border: "1px solid #FCD34D",
              }}
            >
              <InlineStack gap="300" align="start" blockAlign="center">
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    minWidth: "40px",
                    minHeight: "40px",
                    padding: "12px",
                    backgroundColor: "#F59E0B15",
                    borderRadius: "16px",
                    border: "2px solid #F59E0B30",
                  }}
                >
                  <Icon source={AlertTriangleIcon} tone="base" />
                </div>
                <BlockStack gap="100">
                  <div style={{ color: "#92400E" }}>
                    <Text as="h3" variant="headingMd" fontWeight="bold">
                      Services Currently Paused
                    </Text>
                  </div>
                  <Text as="p" variant="bodyMd" tone="subdued">
                    Your Better Bundle features are paused until billing is
                    configured. Setup takes less than 2 minutes.
                  </Text>
                </BlockStack>
              </InlineStack>
            </div>

            {/* Plan Details */}
            <div
              style={{
                padding: "20px",
                backgroundColor: "#F8FAFC",
                borderRadius: "12px",
                border: "1px solid #E2E8F0",
              }}
            >
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
                      💡 Usage-Based Billing Plan
                    </Text>
                  </div>
                </div>

                <BlockStack gap="200">
                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Commission Rate:
                    </Text>
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      3% of attributed revenue
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

                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm" tone="subdued">
                      When You Pay:
                    </Text>
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      Only when you make sales
                    </Text>
                  </InlineStack>
                </BlockStack>

                <div
                  style={{
                    padding: "12px",
                    backgroundColor: "#FFFFFF",
                    borderRadius: "8px",
                    border: "1px solid #E2E8F0",
                  }}
                >
                  <Text as="p" variant="bodySm" tone="subdued">
                    ✅ Cancel anytime • No hidden fees • Pay for value delivered
                  </Text>
                </div>
              </BlockStack>
            </div>

            {/* Spending Limit Section */}
            <div
              style={{
                padding: "20px",
                backgroundColor: "#FFFFFF",
                borderRadius: "12px",
                border: "2px solid #3B82F6",
              }}
            >
              <BlockStack gap="400">
                <InlineStack gap="200" align="start" blockAlign="center">
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      minWidth: "40px",
                      minHeight: "40px",
                      padding: "12px",
                      backgroundColor: "#3B82F615",
                      borderRadius: "16px",
                      border: "2px solid #3B82F630",
                    }}
                  >
                    <Icon source={CreditCardIcon} tone="base" />
                  </div>
                  <BlockStack gap="100">
                    <Text as="h3" variant="headingMd" fontWeight="bold">
                      Choose Your Monthly Spending Cap
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      This is the maximum you'll be charged per month. You can
                      change this anytime.
                    </Text>
                  </BlockStack>
                </InlineStack>

                <div style={{ paddingTop: "8px" }}>
                  <Text as="p" variant="headingLg" fontWeight="bold">
                    {formatCurrency(displayValue)}
                  </Text>
                </div>

                <TextField
                  label="Monthly Spending Cap"
                  type="number"
                  value={displayValue.toString()}
                  onChange={(value) => {
                    const numValue = parseFloat(value);
                    if (!isNaN(numValue) && numValue > 0) {
                      setSpendingLimit(value);
                    }
                  }}
                  suffix={shopCurrency}
                  helpText="Enter your monthly spending limit"
                  autoComplete="off"
                />

                <div
                  style={{
                    padding: "12px",
                    backgroundColor: "#F0F9FF",
                    borderRadius: "8px",
                    border: "1px solid #BAE6FD",
                  }}
                >
                  <Text as="p" variant="bodySm" tone="subdued">
                    💡 With a {formatCurrency(displayValue)} monthly cap, you'll
                    never pay more than that—even if your 3% commission exceeds
                    it. This cap lets you handle up to{" "}
                    <strong>{formatCurrency(revenueCapacity)}</strong> in
                    monthly attributed revenue.
                  </Text>
                </div>
              </BlockStack>
            </div>

            {/* Error Display */}
            {error && (
              <Banner tone="critical">
                <Text as="p">{error}</Text>
              </Banner>
            )}

            {/* Action Buttons */}
            <BlockStack gap="300">
              <Button
                variant="primary"
                size="large"
                onClick={handleSetupBilling}
                loading={isLoading}
                fullWidth
              >
                Continue to Shopify Approval
              </Button>

              <Text as="p" variant="bodySm" tone="subdued" alignment="center">
                You'll be redirected to Shopify to review and approve your
                billing setup
              </Text>
            </BlockStack>
          </BlockStack>
        </div>
      </Card>

      {/* Help Section */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "24px",
        }}
      >
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
                    ℹ️ How It Works
                  </Text>
                </div>
              </div>
              <BlockStack gap="200">
                <Text as="p" variant="bodySm">
                  <strong>1.</strong> Choose your monthly spending cap
                </Text>
                <Text as="p" variant="bodySm">
                  <strong>2.</strong> Click "Continue to Shopify Approval"
                </Text>
                <Text as="p" variant="bodySm">
                  <strong>3.</strong> Review and approve in Shopify
                </Text>
                <Text as="p" variant="bodySm">
                  <strong>4.</strong> Services resume automatically
                </Text>
              </BlockStack>
            </BlockStack>
          </div>
        </Card>

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
                    💡 Good to Know
                  </Text>
                </div>
              </div>
              <BlockStack gap="200">
                <Text as="p" variant="bodySm" tone="subdued">
                  <strong>Safe & Predictable:</strong> Your spending cap
                  protects you from unexpected charges.
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  <strong>Flexible:</strong> Change your spending cap anytime or
                  cancel with no penalties.
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  <strong>Fair Pricing:</strong> Only pay 3% when Better Bundle
                  generates revenue for you.
                </Text>
              </BlockStack>
            </BlockStack>
          </div>
        </Card>
      </div>
    </BlockStack>
  );
}
