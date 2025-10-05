import {
  Card,
  BlockStack,
  Text,
  Select,
  Button,
  Banner,
  InlineStack,
  Icon,
} from "@shopify/polaris";
import { AlertTriangleIcon } from "@shopify/polaris-icons";
import { BillingLayout } from "./BillingLayout";

interface SubscriptionCancelledProps {
  spendingLimit: string;
  setSpendingLimit: (value: string) => void;
  handleSetupBilling: () => void;
  isLoading: boolean;
}

export function SubscriptionCancelled({
  spendingLimit,
  setSpendingLimit,
  handleSetupBilling,
  isLoading,
}: SubscriptionCancelledProps) {
  return (
    <BillingLayout>
      <Banner tone="critical">
        <InlineStack gap="200" align="start">
          <Icon source={AlertTriangleIcon} tone="critical" />
          <Text as="p" variant="bodyMd" fontWeight="bold">
            Subscription Cancelled - Services Paused
          </Text>
        </InlineStack>
      </Banner>

      <Card>
        <div style={{ padding: "24px" }}>
          <BlockStack gap="400">
            <Text as="h2" variant="headingMd">
              Resume Services
            </Text>

            <div
              style={{
                padding: "20px",
                backgroundColor: "#F0F9FF",
                borderRadius: "8px",
                border: "1px solid #0EA5E9",
                marginBottom: "16px",
              }}
            >
              <BlockStack gap="200">
                <Text as="p" variant="bodyMd" fontWeight="bold">
                  Usage-Based Billing: 3% of revenue, capped monthly
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  • Cancel anytime • No surprise charges • Pay for value
                  delivered
                </Text>
              </BlockStack>
            </div>

            <Select
              label="Monthly spending limit"
              value={spendingLimit}
              onChange={setSpendingLimit}
              options={[
                { label: "$100 USD", value: "100" },
                { label: "$250 USD", value: "250" },
                { label: "$500 USD", value: "500" },
                { label: "$1,000 USD", value: "1000" },
                { label: "$2,500 USD", value: "2500" },
                { label: "$5,000 USD", value: "5000" },
              ]}
            />

            <Button
              variant="primary"
              onClick={handleSetupBilling}
              loading={isLoading}
              fullWidth
            >
              Setup New Billing & Resume Services
            </Button>

            <Text as="p" variant="bodySm" tone="subdued" alignment="center">
              You'll be redirected to Shopify to approve the billing
            </Text>
          </BlockStack>
        </div>
      </Card>
    </BillingLayout>
  );
}
