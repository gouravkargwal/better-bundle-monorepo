import {
  Card,
  BlockStack,
  Text,
  Button,
  Banner,
  InlineStack,
  Icon,
} from "@shopify/polaris";
import { ClockIcon } from "@shopify/polaris-icons";
import { BillingLayout } from "./BillingLayout";

interface SubscriptionPendingProps {
  billingPlan: any;
  handleCancelSubscription: () => void;
  isLoading: boolean;
}

export function SubscriptionPending({
  billingPlan,
  handleCancelSubscription,
  isLoading,
}: SubscriptionPendingProps) {
  return (
    <BillingLayout>
      <Banner tone="info">
        <InlineStack gap="200" align="start">
          <Icon source={ClockIcon} tone="info" />
          <Text as="p" variant="bodyMd" fontWeight="bold">
            Subscription Pending Approval
          </Text>
        </InlineStack>
      </Banner>

      <Card>
        <div style={{ padding: "24px" }}>
          <BlockStack gap="400">
            <div
              style={{
                padding: "20px",
                backgroundColor: "#FEF3C7",
                borderRadius: "8px",
                border: "1px solid #F59E0B",
                marginBottom: "16px",
              }}
            >
              <InlineStack gap="200" align="start">
                <Icon source={ClockIcon} tone="warning" />
                <Text as="p" variant="bodyMd" fontWeight="bold">
                  Next: Approve subscription in Shopify
                </Text>
              </InlineStack>
            </div>

            <Text as="h2" variant="headingMd">
              Approve Your Subscription
            </Text>

            {billingPlan.subscription_confirmation_url && (
              <Button
                variant="primary"
                onClick={() =>
                  window.open(
                    billingPlan.subscription_confirmation_url || "",
                    "_top",
                  )
                }
                fullWidth
              >
                Approve Subscription in Shopify
              </Button>
            )}

            <InlineStack gap="200" align="center">
              <Button
                variant="tertiary"
                onClick={() => window.location.reload()}
                loading={isLoading}
              >
                Check Status
              </Button>
              <Button
                variant="secondary"
                tone="critical"
                onClick={handleCancelSubscription}
                loading={isLoading}
              >
                Cancel Subscription
              </Button>
            </InlineStack>

            <Text as="p" variant="bodySm" tone="subdued" alignment="center">
              Already approved? Click to refresh
            </Text>

            <Text as="p" variant="bodySm" tone="subdued" alignment="center">
              Services will automatically resume after approval
            </Text>
          </BlockStack>
        </div>
      </Card>
    </BillingLayout>
  );
}
