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
      <Card>
        <div
          style={{
            padding: "40px 32px",
            textAlign: "center",
            background: "linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%)",
            borderRadius: "16px",
            border: "1px solid #E2E8F0",
          }}
        >
          <div
            style={{
              display: "inline-block",
              padding: "12px",
              backgroundColor: "#3B82F615",
              borderRadius: "12px",
              marginBottom: "16px",
            }}
          >
            <Icon source={ClockIcon} tone="base" />
          </div>
          <div style={{ color: "#1E293B" }}>
            <Text as="h3" variant="headingLg" fontWeight="bold">
              📋 No Billing Events Yet
            </Text>
          </div>
          <div style={{ marginTop: "12px" }}>
            <Text as="p" variant="bodyLg" tone="subdued">
              Billing events will appear here as they occur. This includes plan
              changes, payments, and other billing activities.
            </Text>
          </div>
        </div>
      </Card>
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
    <BlockStack gap="300">
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
                  📋 Recent Billing Events
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
                <div
                  key={event.id}
                  style={{
                    padding: "20px",
                    backgroundColor: "#FFFFFF",
                    borderRadius: "12px",
                    border: "1px solid #E2E8F0",
                    boxShadow:
                      "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)",
                    transition: "all 0.2s ease-in-out",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = "translateY(-1px)";
                    e.currentTarget.style.boxShadow =
                      "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = "translateY(0)";
                    e.currentTarget.style.boxShadow =
                      "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)";
                  }}
                >
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
                    </InlineStack>
                    <BlockStack gap="100">
                      <InlineStack align="space-between" blockAlign="center">
                        <div style={{ color: "#1E293B" }}>
                          <Text as="p" variant="bodyMd" fontWeight="medium">
                            {event.type.replace(/_/g, " ").toUpperCase()}
                          </Text>
                        </div>
                        <Badge
                          tone={getEventBadgeTone(event.type)}
                          size="small"
                        >
                          {event.type.replace(/_/g, " ")}
                        </Badge>
                      </InlineStack>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {formatDate(event.occurred_at)}
                      </Text>
                    </BlockStack>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        minWidth: "32px",
                        minHeight: "32px",
                        padding: "6px",
                        backgroundColor: "#10B98115",
                        borderRadius: "8px",
                        border: "1px solid #10B98130",
                      }}
                    >
                      <Icon source={CheckIcon} tone="base" />
                    </div>
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
