import { useState, useEffect } from "react";
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
  const [timeRemaining, setTimeRemaining] = useState<string>("");

  // Add null check for trialData
  if (!trialData) {
    return (
      <div style={{ padding: "24px", textAlign: "center" }}>
        <Text as="p">Trial data not available</Text>
      </div>
    );
  }

  const daysRemaining = trialData.daysRemaining;
  const trialDays = trialData.trialDays;
  const trialProgress =
    trialDays > 0
      ? Math.max(0, Math.min(100, ((trialDays - daysRemaining) / trialDays) * 100))
      : 0;
  const isExpiringSoon = daysRemaining <= 3 && daysRemaining > 0;
  const isExpired = daysRemaining <= 0;

  // Update countdown every minute
  useEffect(() => {
    const updateRemaining = () => {
      if (daysRemaining > 0) {
        const totalHours = daysRemaining * 24;
        if (totalHours >= 24) {
          setTimeRemaining(`${daysRemaining} days`);
        } else if (totalHours >= 1) {
          setTimeRemaining(`${Math.floor(totalHours)} hours`);
        } else {
          setTimeRemaining("Less than an hour");
        }
      } else {
        setTimeRemaining("Expired");
      }
    };

    updateRemaining();
    const interval = setInterval(updateRemaining, 60000);
    return () => clearInterval(interval);
  }, [daysRemaining]);

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
                Drive sales with Better Bundle — completely free for{" "}
                {trialDays} days
              </Text>
            </BlockStack>
            <Badge
              tone={isExpiringSoon ? "warning" : "success"}
              size="large"
            >
              {isExpiringSoon ? "Expiring Soon" : "Active"}
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
                backgroundColor: isExpiringSoon ? "#FEF3C7" : "#F0FDF4",
                borderRadius: "12px",
                border: `2px solid ${
                  isExpiringSoon ? "#F59E0B" : "#22C55E"
                }`,
              }}
            >
              <BlockStack gap="400">
                {/* Time Stats */}
                <InlineStack align="space-between" blockAlign="end">
                  <BlockStack gap="100">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Time Remaining
                    </Text>
                    <Text as="h3" variant="headingLg" fontWeight="bold">
                      {timeRemaining}
                    </Text>
                  </BlockStack>
                  <BlockStack gap="100" align="end">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Trial Period
                    </Text>
                    <Text as="p" variant="headingMd" fontWeight="semibold">
                      {daysRemaining} of {trialDays} days
                    </Text>
                  </BlockStack>
                </InlineStack>

                {/* Progress Bar */}
                <BlockStack gap="200">
                  <ProgressBar
                    progress={Math.min(trialProgress, 100)}
                    tone={isExpiringSoon ? "warning" : "success"}
                    size="medium"
                  />
                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm" fontWeight="medium">
                      {Math.min(trialProgress, 100).toFixed(0)}% Complete
                    </Text>
                    {!isExpired && (
                      <Text as="p" variant="bodySm" tone="subdued">
                        {daysRemaining} days remaining
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
                  When trial ends, choose your plan to continue
                </Text>
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                <Text as="span">3.</Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  Pay a flat monthly fee — predictable and simple
                </Text>
              </div>
            </BlockStack>
          </BlockStack>
        </Card>
      </div>
    </BlockStack>
  );
}
