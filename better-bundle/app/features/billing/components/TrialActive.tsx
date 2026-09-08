import {
  Card,
  BlockStack,
  InlineStack,
  Text,
  Badge,
  ProgressBar,
} from "@shopify/polaris";
import { CheckCircleIcon } from "@shopify/polaris-icons";
import type { TrialData } from "../types/billing.types";

interface TrialActiveProps {
  trialData: TrialData | undefined;
  shopCurrency: string;
}

export function TrialActive({ trialData, shopCurrency }: TrialActiveProps) {
  // Add null check for trialData
  if (!trialData) {
    return (
      <div style={{ padding: "24px", textAlign: "center" }}>
        <Text as="p">Trial data not available</Text>
      </div>
    );
  }

  // Progress is revenue, not time — the trial ends when we have driven
  // `trialThreshold` of attributed sales, however long that takes.
  const { revenueEarned, trialThreshold } = trialData;
  const remaining = Math.max(0, trialThreshold - revenueEarned);
  const trialProgress =
    trialThreshold > 0
      ? Math.max(0, Math.min(100, (revenueEarned / trialThreshold) * 100))
      : 0;
  const nearingThreshold = trialProgress >= 80 && trialProgress < 100;

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: shopCurrency,
      maximumFractionDigits: 0,
    }).format(amount);

  return (
    <BlockStack gap="500">
      {/* Status Header */}
      <Card>
        <BlockStack gap="300">
          <InlineStack align="space-between" blockAlign="center">
            <BlockStack gap="100">
              <Text variant="headingMd" as="h3">
                🚀 Free Trial Active
              </Text>
              <Text as="p" tone="subdued">
                Free until Better Bundle has driven{" "}
                {formatCurrency(trialThreshold)} in attributed sales
              </Text>
            </BlockStack>
            <Badge tone={nearingThreshold ? "attention" : "success"} size="large">
              {nearingThreshold ? "Nearly There" : "Active"}
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
                backgroundColor: nearingThreshold ? "#FEF3C7" : "#F0FDF4",
                borderRadius: "12px",
                border: `2px solid ${nearingThreshold ? "#F59E0B" : "#22C55E"}`,
              }}
            >
              <BlockStack gap="400">
                {/* Time Stats */}
                <InlineStack align="space-between" blockAlign="end">
                  <BlockStack gap="100">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Revenue Generated
                    </Text>
                    <Text as="h3" variant="headingLg" fontWeight="bold">
                      {formatCurrency(revenueEarned)}
                    </Text>
                  </BlockStack>
                  <BlockStack gap="100" align="end">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Free Until
                    </Text>
                    <Text as="p" variant="headingMd" fontWeight="semibold">
                      {formatCurrency(trialThreshold)}
                    </Text>
                  </BlockStack>
                </InlineStack>

                {/* Progress Bar */}
                <BlockStack gap="200">
                  <ProgressBar
                    progress={Math.min(trialProgress, 100)}
                    tone="success"
                    size="medium"
                  />
                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm" fontWeight="medium">
                      {Math.min(trialProgress, 100).toFixed(0)}% Complete
                    </Text>
                    {remaining > 0 && (
                      <Text as="p" variant="bodySm" tone="subdued">
                        {formatCurrency(remaining)} to go
                      </Text>
                    )}
                  </InlineStack>
                </BlockStack>
              </BlockStack>
            </div>
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
                  Continue using all features completely free during trial
                </Text>
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                <Text as="span">2.</Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  Once we&apos;ve driven {formatCurrency(trialThreshold)},
                  approve billing in Shopify to keep going
                </Text>
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                <Text as="span">3.</Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  After that you pay a share of the sales we generate — nothing
                  if we generate nothing
                </Text>
              </div>
            </BlockStack>
          </BlockStack>
        </Card>
      </div>
    </BlockStack>
  );
}
