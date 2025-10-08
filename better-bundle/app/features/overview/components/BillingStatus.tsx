// features/overview/components/BillingStatus.tsx
import { Card, Text, BlockStack, Badge } from "@shopify/polaris";

interface BillingStatusProps {
  billingPlan: {
    name: string;
    status: string;
  };
}

export function BillingStatus({ billingPlan }: BillingStatusProps) {
  return (
    <Card>
      <div style={{ padding: "20px" }}>
        <BlockStack gap="300">
          <div
            style={{
              padding: "20px",
              backgroundColor: "#F0F9FF",
              borderRadius: "12px",
              border: "1px solid #BAE6FD",
            }}
          >
            <div style={{ color: "#0C4A6E" }}>
              <Text as="h3" variant="headingMd" fontWeight="bold">
                💳 Billing Status
              </Text>
            </div>
            <div style={{ marginTop: "8px" }}>
              <Text as="p" variant="bodyMd" tone="subdued">
                {billingPlan.name} • {billingPlan.status}
              </Text>
            </div>
            <div style={{ marginTop: "16px" }}>
              <Badge tone="success" size="large">
                Active
              </Badge>
            </div>
          </div>
        </BlockStack>
      </div>
    </Card>
  );
}
