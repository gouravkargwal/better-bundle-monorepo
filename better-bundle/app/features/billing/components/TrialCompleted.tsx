import { useState } from "react";
import {
  BlockStack,
  Button,
  Card,
  InlineStack,
  Text,
  Icon,
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
      // Use default plan selection — in a more advanced UI, you'd let the user choose
      const setupData: BillingSetupData = {
        planName: "Pro",
        monthlyFee: 29,
        trialDays: trialData.trialDays || 14,
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
                Your free trial has ended. Select a plan to continue using
                Better Bundle.
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
                      💡 Flat Rate Pricing Plan
                    </Text>
                  </div>
                </div>

                <BlockStack gap="200">
                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Plan:
                    </Text>
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      Pro
                    </Text>
                  </InlineStack>

                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Price:
                    </Text>
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      {formatCurrency(29)}/month
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
                      What You Get:
                    </Text>
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      Full access to all features
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
                    ✅ Cancel anytime • No hidden fees • Predictable monthly
                    pricing
                  </Text>
                </div>
              </BlockStack>
            </div>

            {/* Plan Selection Card */}
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
                      Continue with Pro Plan
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      {formatCurrency(29)}/month — full access to all features
                    </Text>
                  </BlockStack>
                </InlineStack>

                <div
                  style={{
                    padding: "16px",
                    backgroundColor: "#F0F9FF",
                    borderRadius: "8px",
                    border: "1px solid #BAE6FD",
                  }}
                >
                  <BlockStack gap="200">
                    <InlineStack gap="200">
                      <Text as="span" variant="bodySm" color="text-success">
                        ✓
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        AI-powered product recommendations
                      </Text>
                    </InlineStack>
                    <InlineStack gap="200">
                      <Text as="span" variant="bodySm" color="text-success">
                        ✓
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Detailed attribution & analytics
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
                  </BlockStack>
                </div>

                <div
                  style={{
                    padding: "12px",
                    backgroundColor: "#FEF3C7",
                    borderRadius: "8px",
                    border: "1px solid #FCD34D",
                  }}
                >
                  <Text as="p" variant="bodySm" tone="subdued">
                    💡 You'll be charged {formatCurrency(29)} per month,
                    automatically billed every 30 days. Cancel anytime.
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
                subscription
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
                  <strong>1.</strong> Click "Continue to Shopify Approval"
                </Text>
                <Text as="p" variant="bodySm">
                  <strong>2.</strong> Review your subscription details in
                  Shopify
                </Text>
                <Text as="p" variant="bodySm">
                  <strong>3.</strong> Approve the recurring charge
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
                  <strong>Predictable Pricing:</strong> One flat monthly fee —
                  no surprises.
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  <strong>Flexible:</strong> Upgrade, downgrade, or cancel
                  anytime with no penalties.
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  <strong>Fair:</strong> Full access to all features for one
                  simple price.
                </Text>
              </BlockStack>
            </BlockStack>
          </div>
        </Card>
      </div>
    </BlockStack>
  );
}
