import { Card, Text, BlockStack, InlineStack, Icon } from "@shopify/polaris";
import { CheckIcon } from "@shopify/polaris-icons";

export function BillingEvents({ billingData, formatDate }: any) {
  const events = billingData?.recent_events || [];

  if (events.length === 0) {
    return (
      <Card>
        <div style={{ padding: "32px", textAlign: "center" }}>
          <Text as="h3" variant="headingMd" fontWeight="bold">
            📋 No Billing Events
          </Text>
          <div style={{ marginTop: "12px" }}>
            <Text as="p" variant="bodyMd" tone="subdued">
              Billing events will appear here as they occur.
            </Text>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <BlockStack gap="400">
      <Card>
        <div style={{ padding: "24px" }}>
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd" fontWeight="bold">
              📋 Recent Billing Events
            </Text>

            <BlockStack gap="300">
              {events.map((event: any, index: number) => (
                <div
                  key={event.id}
                  style={{
                    padding: "16px",
                    backgroundColor: "#F8FAFC",
                    borderRadius: "8px",
                    border: "1px solid #E2E8F0",
                  }}
                >
                  <InlineStack align="space-between" blockAlign="center">
                    <BlockStack gap="100">
                      <Text as="p" variant="bodyMd" fontWeight="medium">
                        {event.type.replace(/_/g, " ").toUpperCase()}
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {formatDate(event.occurred_at)}
                      </Text>
                    </BlockStack>
                    <Icon source={CheckIcon} tone="base" />
                  </InlineStack>
                </div>
              ))}
            </BlockStack>
          </BlockStack>
        </div>
      </Card>
    </BlockStack>
  );
}
