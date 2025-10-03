import {
  Card,
  Text,
  BlockStack,
  InlineStack,
  Icon,
  Badge,
} from "@shopify/polaris";
import { CheckIcon, ClockIcon, AlertCircleIcon } from "@shopify/polaris-icons";

export function BillingEvents({ billingData, formatDate }: any) {
  const events = billingData?.recent_events || [];

  if (events.length === 0) {
    return (
      <BlockStack gap="400">
        <div
          style={{
            padding: "24px",
            backgroundColor: "#F8FAFC",
            borderRadius: "12px",
            border: "1px solid #E2E8F0",
          }}
        >
          <div style={{ color: "#1E293B" }}>
            <Text as="h2" variant="headingLg" fontWeight="bold">
              Recent Billing Events
            </Text>
          </div>
          <div style={{ marginTop: "8px" }}>
            <Text as="p" variant="bodyMd" tone="subdued">
              Track your billing activity and plan changes
            </Text>
          </div>
        </div>

        <Card>
          <div
            style={{
              padding: "40px 32px",
              textAlign: "center",
            }}
          >
            <div
              style={{
                display: "inline-block",
                padding: "12px",
                backgroundColor: "#F8FAFC",
                borderRadius: "12px",
                marginBottom: "16px",
                border: "1px solid #E2E8F0",
              }}
            >
              <Icon source={ClockIcon} tone="base" />
            </div>
            <div style={{ color: "#1E293B" }}>
              <Text as="h3" variant="headingLg" fontWeight="bold">
                No Billing Events Yet
              </Text>
            </div>
            <div style={{ marginTop: "12px" }}>
              <Text as="p" variant="bodyLg" tone="subdued">
                Billing events will appear here as they occur. This includes
                plan changes, payments, and other billing activities.
              </Text>
            </div>
          </div>
        </Card>
      </BlockStack>
    );
  }

  const getEventIcon = (eventType: string) => {
    switch (eventType.toLowerCase()) {
      case "plan_updated":
      case "plan_created":
        return CheckIcon;
      case "payment_failed":
      case "billing_error":
        return AlertCircleIcon;
      default:
        return ClockIcon;
    }
  };

  const getEventBadgeTone = (eventType: string) => {
    switch (eventType.toLowerCase()) {
      case "plan_updated":
      case "plan_created":
        return "success";
      case "payment_failed":
      case "billing_error":
        return "critical";
      default:
        return "info";
    }
  };

  return (
    <BlockStack gap="400">
      <div
        style={{
          padding: "24px",
          backgroundColor: "#F8FAFC",
          borderRadius: "12px",
          border: "1px solid #E2E8F0",
        }}
      >
        <div style={{ color: "#1E293B" }}>
          <Text as="h2" variant="headingLg" fontWeight="bold">
            Recent Billing Events
          </Text>
        </div>
        <div style={{ marginTop: "8px" }}>
          <Text as="p" variant="bodyMd" tone="subdued">
            Track your billing activity and plan changes
          </Text>
        </div>
      </div>

      <BlockStack gap="200">
        {events.map((event: any, index: number) => (
          <Card key={event.id}>
            <InlineStack align="space-between" blockAlign="center">
              <InlineStack gap="300" blockAlign="center">
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    minWidth: "40px",
                    minHeight: "40px",
                    padding: "8px",
                    backgroundColor: "#F8FAFC",
                    borderRadius: "10px",
                    border: "1px solid #E2E8F0",
                  }}
                >
                  <Icon source={getEventIcon(event.type)} tone="base" />
                </div>
                <BlockStack gap="100">
                  <Text as="p" variant="bodyMd" fontWeight="medium">
                    {event.type.replace(/_/g, " ").toUpperCase()}
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    {formatDate(event.occurred_at)}
                  </Text>
                </BlockStack>
              </InlineStack>
              <Badge tone={getEventBadgeTone(event.type)} size="small">
                {event.type.replace(/_/g, " ")}
              </Badge>
            </InlineStack>
          </Card>
        ))}
      </BlockStack>
    </BlockStack>
  );
}
