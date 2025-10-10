// features/overview/components/QuickActions.tsx
import { Card, Text, BlockStack, Button } from "@shopify/polaris";
import {
  ChartCohortIcon,
  SettingsIcon,
  BillIcon,
} from "@shopify/polaris-icons";

export function QuickActions() {
  return (
    <Card>
      <div style={{ padding: "20px" }}>
        <BlockStack gap="300">
          <div
            style={{
              padding: "20px",
              backgroundColor: "#FEF3C7",
              borderRadius: "12px",
              border: "1px solid #FCD34D",
            }}
          >
            <div style={{ color: "#92400E" }}>
              <Text as="h3" variant="headingMd" fontWeight="bold">
                🚀 Quick Actions
              </Text>
            </div>
            <div style={{ marginTop: "8px" }}>
              <Text as="p" variant="bodyMd" tone="subdued">
                Get the most out of your AI recommendations
              </Text>
            </div>
          </div>

          <BlockStack gap="200">
            <Button
              url="/app/dashboard"
              variant="primary"
              size="large"
              icon={ChartCohortIcon}
            >
              View Full Analytics
            </Button>
            <Button
              url="/app/extensions"
              variant="secondary"
              size="large"
              icon={SettingsIcon}
            >
              Manage Extensions
            </Button>
            <Button
              url="/app/billing"
              variant="tertiary"
              size="large"
              icon={BillIcon}
            >
              Billing
            </Button>
          </BlockStack>
        </BlockStack>
      </div>
    </Card>
  );
}
