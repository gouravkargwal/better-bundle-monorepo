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
import type { TrialData } from "../types/billing.types";

interface TrialActiveProps {
  trialData: TrialData | undefined;
  shopCurrency: string;
  onSetupBilling: () => Promise<{ success: boolean; error?: string }>;
}

export function TrialActive({
  trialData,
  shopCurrency,
  onSetupBilling,
}: TrialActiveProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: shopCurrency,
    }).format(amount);
  };

  if (!trialData) {
    return (
      <div style={{ padding: "24px", textAlign: "center" }}>
        <Text as="p">Trial data not available</Text>
      </div>
    );
  }

  const handleSetupBilling = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await onSetupBilling();
      if (!result.success) {
        setError(result.error || "Failed to start trial");
      }
    } catch (err) {
      setError("An unexpected error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <BlockStack gap="500">
      <Card>
        <BlockStack gap="300">
          <InlineStack align="space-between" blockAlign="center">
            <BlockStack gap="100">
              <Text variant="headingMd" as="h3">
                🚀 Start Your Free Trial
              </Text>
              <Text as="p" tone="subdued">
                Try BetterBundle free for {trialData.trialDays} days — no
                charge until your trial ends.
              </Text>
            </BlockStack>
            <Badge tone="success" size="large">
              Available
            </Badge>
          </InlineStack>
        </BlockStack>
      </Card>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "2fr 1fr",
          gap: "var(--p-space-400)",
        }}
      >
        <Card>
          <BlockStack gap="400">
            <Text as="h2" variant="headingMd" fontWeight="semibold">
              Plan Details
            </Text>
            <div
              style={{
                padding: "20px",
                backgroundColor: "#F0FDF4",
                borderRadius: "12px",
                border: "2px solid #22C55E",
              }}
            >
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="end">
                  <BlockStack gap="100">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Free trial length
                    </Text>
                    <Text as="h3" variant="headingLg" fontWeight="bold">
                      {trialData.trialDays} days
                    </Text>
                  </BlockStack>
                  <BlockStack gap="100" align="end">
                    <Text as="p" variant="bodySm" tone="subdued">
                      After trial
                    </Text>
                    <Text as="p" variant="headingMd" fontWeight="semibold">
                      {formatCurrency(trialData.monthlyPrice)}/mo
                    </Text>
                  </BlockStack>
                </InlineStack>
              </BlockStack>
            </div>

            {error && (
              <Banner tone="critical">
                <Text as="p">{error}</Text>
              </Banner>
            )}

            <Button
              variant="primary"
              size="large"
              onClick={handleSetupBilling}
              loading={isLoading}
              fullWidth
            >
              Start Free Trial
            </Button>
            <Text as="p" variant="bodySm" tone="subdued" alignment="center">
              You'll be redirected to Shopify to approve your subscription —
              no charge until your {trialData.trialDays}-day trial ends.
            </Text>
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="300">
            <Text as="h3" variant="headingMd" fontWeight="semibold">
              💡 What's Next?
            </Text>
            <BlockStack gap="200">
              <div style={{ display: "flex", gap: "8px" }}>
                <Text as="span">1.</Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  Approve billing setup in Shopify to start your trial
                </Text>
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                <Text as="span">2.</Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  Use all features free for {trialData.trialDays} days
                </Text>
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                <Text as="span">3.</Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  After your trial, pay {formatCurrency(trialData.monthlyPrice)}
                  /mo — 50% off your first month
                </Text>
              </div>
            </BlockStack>
          </BlockStack>
        </Card>
      </div>
    </BlockStack>
  );
}
