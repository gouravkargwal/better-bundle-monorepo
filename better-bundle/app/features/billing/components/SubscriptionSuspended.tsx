import {
  Card,
  BlockStack,
  Text,
  InlineStack,
  Button,
  Banner,
  Badge,
} from "@shopify/polaris";
import { AlertTriangleIcon, RefreshIcon } from "@shopify/polaris-icons";
import type { SubscriptionData } from "../types/billing.types";

interface SubscriptionSuspendedProps {
  subscriptionData: SubscriptionData;
  shopCurrency: string;
  onReactivate: () => Promise<{ success: boolean; error?: string }>;
}

export function SubscriptionSuspended({
  subscriptionData,
  shopCurrency,
  onReactivate,
}: SubscriptionSuspendedProps) {
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: shopCurrency,
    }).format(amount);
  };

  const handleReactivate = () => {
    // This would typically redirect to a reactivation flow
    window.location.href = "/app/billing?action=reactivate";
  };

  return (
    <BlockStack gap="500">
      {/* Status Header */}
      <Card>
        <BlockStack gap="300">
          <InlineStack align="space-between" blockAlign="center">
            <BlockStack gap="100">
              <Text variant="headingMd" as="h3">
                ⚠️ Services Suspended
              </Text>
              <Text as="p" tone="subdued">
                Your Better Bundle services are currently suspended. Reactivate
                to continue using all features.
              </Text>
            </BlockStack>
            <Badge tone="critical" size="large">
              Suspended
            </Badge>
          </InlineStack>
        </BlockStack>
      </Card>

      <Card>
        <div style={{ padding: "24px" }}>
          <BlockStack gap="500">
            {/* Header */}
            <InlineStack align="space-between" blockAlign="center">
              <div>
                <Text as="h2" variant="headingMd" fontWeight="semibold">
                  Subscription Suspended
                </Text>
                <Text as="p" variant="bodyMd" tone="subdued">
                  Your Better Bundle services are currently paused
                </Text>
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <AlertTriangleIcon />
                <Text as="span" variant="bodyMd" tone="critical">
                  Suspended
                </Text>
              </div>
            </InlineStack>

            <Banner tone="critical">
              <Text as="p">
                BetterBundle services are currently suspended. Please contact
                support or reactivate your subscription to continue.
              </Text>
            </Banner>

            {/* Subscription Details */}
            <div
              style={{
                padding: "20px",
                backgroundColor: "#FEF2F2",
                borderRadius: "12px",
                border: "1px solid #FECACA",
              }}
            >
              <BlockStack gap="300">
                <Text as="h3" variant="headingMd" fontWeight="semibold">
                  Subscription Details
                </Text>
                <BlockStack gap="200">
                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Status:
                    </Text>
                    <Text as="p" variant="bodyMd" fontWeight="semibold">
                      Suspended
                    </Text>
                  </InlineStack>
                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Monthly Cap:
                    </Text>
                    <Text as="p" variant="bodyMd" fontWeight="semibold">
                      {formatCurrency(subscriptionData.spendingLimit)}
                    </Text>
                  </InlineStack>
                  <InlineStack align="space-between">
                    <Text as="p" variant="bodySm" tone="subdued">
                      Last Usage:
                    </Text>
                    <Text as="p" variant="bodyMd" fontWeight="semibold">
                      {formatCurrency(subscriptionData.currentUsage)}
                    </Text>
                  </InlineStack>
                </BlockStack>
              </BlockStack>
            </div>

            {/* Action Buttons */}
            <BlockStack gap="300">
              <Button
                variant="primary"
                size="large"
                onClick={handleReactivate}
                icon={RefreshIcon}
                fullWidth
              >
                Reactivate Subscription
              </Button>

              <Button
                variant="tertiary"
                onClick={() => (window.location.href = "/app/support")}
              >
                Contact Support
              </Button>
            </BlockStack>

            {/* Info */}
            <div
              style={{
                padding: "16px",
                backgroundColor: "#FEF3C7",
                borderRadius: "8px",
                border: "1px solid #FDE68A",
              }}
            >
              <Text as="p" variant="bodyMd">
                <strong>Why was my subscription suspended?</strong> This usually
                happens due to payment issues, reaching your spending cap, or
                manual suspension. Contact support for assistance.
              </Text>
            </div>
          </BlockStack>
        </div>
      </Card>
    </BlockStack>
  );
}
