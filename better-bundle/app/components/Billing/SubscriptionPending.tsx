import {
  Card,
  BlockStack,
  Text,
  Button,
  Banner,
  InlineStack,
  Icon,
  Badge,
} from "@shopify/polaris";
import { useFetcher } from "@remix-run/react";
import { ClockIcon, AlertTriangleIcon } from "@shopify/polaris-icons";
import { BillingLayout } from "./BillingLayout";
import { HeroHeader } from "../UI/HeroHeader";
import { formatCurrency } from "app/utils/currency";

interface SubscriptionPendingProps {
  billingPlan: any;
  isLoading: boolean;
  handleCancelSubscription: () => void;
}

export function SubscriptionPending({
  billingPlan,
  isLoading,
  handleCancelSubscription,
}: SubscriptionPendingProps) {
  const fetcher = useFetcher();
  const cappedAmount = billingPlan?.configuration?.capped_amount || 1000;
  const currency = billingPlan?.currency || "USD";

  return (
    <BillingLayout>
      <BlockStack gap="500">
        <HeroHeader
          badge="🕒 Action Required"
          title="Subscription Approval Pending"
          subtitle="Complete the approval process in Shopify to activate your usage-based billing"
          gradient="orange"
        />

        {/* Main Action Card */}
        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="400">
              {/* Status Banner */}
              <div
                style={{
                  padding: "20px",
                  backgroundColor: "#FEF3C7",
                  borderRadius: "12px",
                  border: "1px solid #FCD34D",
                }}
              >
                <BlockStack gap="300">
                  <InlineStack gap="300" align="start" blockAlign="center">
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        minWidth: "40px",
                        minHeight: "40px",
                        padding: "12px",
                        backgroundColor: "#F59E0B15",
                        borderRadius: "16px",
                        border: "2px solid #F59E0B30",
                      }}
                    >
                      <Icon source={ClockIcon} tone="base" />
                    </div>
                    <BlockStack gap="100">
                      <div style={{ color: "#92400E" }}>
                        <Text as="h3" variant="headingMd" fontWeight="bold">
                          Next Step: Approve Subscription in Shopify
                        </Text>
                      </div>
                      <Text as="p" variant="bodyMd" tone="subdued">
                        Your usage-based subscription is waiting for approval by
                        a store owner or admin
                      </Text>
                    </BlockStack>
                    <Badge tone="attention" size="large">
                      Pending
                    </Badge>
                  </InlineStack>
                </BlockStack>
              </div>

              {/* Plan Details */}
              <div
                style={{
                  padding: "20px",
                  backgroundColor: "#F8FAFC",
                  borderRadius: "12px",
                  border: "1px solid #E2E8F0",
                }}
              >
                <BlockStack gap="300">
                  <InlineStack align="space-between" blockAlign="center">
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySm" tone="subdued">
                        Usage-Based Billing Plan
                      </Text>
                      <Text as="h3" variant="headingLg" fontWeight="bold">
                        3% of Attributed Revenue
                      </Text>
                    </BlockStack>
                    <Badge tone="info">Ready for Approval</Badge>
                  </InlineStack>

                  <div
                    style={{
                      padding: "16px",
                      backgroundColor: "#FFFFFF",
                      borderRadius: "8px",
                      border: "1px solid #E2E8F0",
                    }}
                  >
                    <BlockStack gap="200">
                      <InlineStack align="space-between">
                        <Text as="p" variant="bodySm" tone="subdued">
                          Monthly Cap:
                        </Text>
                        <Text as="p" variant="bodyMd" fontWeight="bold">
                          {formatCurrency(cappedAmount, currency)}
                        </Text>
                      </InlineStack>
                      <InlineStack align="space-between">
                        <Text as="p" variant="bodySm" tone="subdued">
                          Billing Cycle:
                        </Text>
                        <Text as="p" variant="bodyMd" fontWeight="bold">
                          Every 30 Days
                        </Text>
                      </InlineStack>
                      <InlineStack align="space-between">
                        <Text as="p" variant="bodySm" tone="subdued">
                          Rate:
                        </Text>
                        <Text as="p" variant="bodyMd" fontWeight="bold">
                          3% of revenue
                        </Text>
                      </InlineStack>
                    </BlockStack>
                  </div>

                  <div
                    style={{
                      padding: "12px",
                      backgroundColor: "#DBEAFE",
                      borderRadius: "8px",
                      border: "1px solid #BAE6FD",
                    }}
                  >
                    <Text as="p" variant="bodySm" tone="subdued">
                      💡 You'll only pay for what you use, up to{" "}
                      {formatCurrency(cappedAmount, currency)} per month. No
                      charges until your customers make purchases through Better
                      Bundle.
                    </Text>
                  </div>
                </BlockStack>
              </div>

              {/* Action Buttons */}
              {billingPlan.subscription_confirmation_url ? (
                <BlockStack gap="300">
                  <Button
                    variant="primary"
                    size="large"
                    onClick={() =>
                      window.open(
                        billingPlan.subscription_confirmation_url || "",
                        "_top",
                      )
                    }
                    fullWidth
                  >
                    Open Shopify Approval Page
                  </Button>
                  <InlineStack gap="200">
                    <fetcher.Form method="post" action="/api/billing/activate">
                      <input
                        type="hidden"
                        name="subscription_id"
                        value={
                          billingPlan?.subscription_id ||
                          billingPlan?.configuration?.subscription_id ||
                          ""
                        }
                      />
                      <Button
                        variant="tertiary"
                        submit
                        loading={fetcher.state !== "idle"}
                      >
                        Check Approval Status
                      </Button>
                    </fetcher.Form>
                  </InlineStack>
                </BlockStack>
              ) : (
                <Banner tone="warning">
                  <BlockStack gap="200">
                    <InlineStack gap="200" align="start">
                      <Icon source={AlertTriangleIcon} tone="warning" />
                      <BlockStack gap="100">
                        <Text as="p" variant="bodyMd" fontWeight="semibold">
                          Approval link not found
                        </Text>
                        <Text as="p" variant="bodySm">
                          Click "Check Approval Status" to refresh. If the issue
                          persists, please return to the billing setup page and
                          try again.
                        </Text>
                      </BlockStack>
                    </InlineStack>
                    <InlineStack gap="200">
                      <fetcher.Form
                        method="post"
                        action="/api/billing/activate"
                      >
                        <input
                          type="hidden"
                          name="subscription_id"
                          value={
                            billingPlan?.subscription_id ||
                            billingPlan?.configuration?.subscription_id ||
                            ""
                          }
                        />
                        <Button
                          variant="primary"
                          submit
                          loading={fetcher.state !== "idle"}
                        >
                          Check Approval Status
                        </Button>
                      </fetcher.Form>
                    </InlineStack>
                  </BlockStack>
                </Banner>
              )}
            </BlockStack>
          </div>
        </Card>

        {/* Help & Info Cards */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
            gap: "24px",
          }}
        >
          {/* What Happens Next */}
          <Card>
            <div style={{ padding: "20px" }}>
              <BlockStack gap="300">
                <div
                  style={{
                    padding: "16px",
                    backgroundColor: "#DBEAFE",
                    borderRadius: "12px",
                    border: "1px solid #BAE6FD",
                  }}
                >
                  <div style={{ color: "#0C4A6E" }}>
                    <Text as="h3" variant="headingMd" fontWeight="bold">
                      ℹ️ What Happens Next
                    </Text>
                  </div>
                </div>
                <BlockStack gap="200">
                  <Text as="p" variant="bodySm">
                    <strong>1.</strong> Click "Open Shopify Approval Page" above
                  </Text>
                  <Text as="p" variant="bodySm">
                    <strong>2.</strong> Review your usage-based billing details
                  </Text>
                  <Text as="p" variant="bodySm">
                    <strong>3.</strong> Click "Approve charge" in Shopify
                  </Text>
                  <Text as="p" variant="bodySm">
                    <strong>4.</strong> Your subscription will activate
                    automatically
                  </Text>
                  <Text as="p" variant="bodySm">
                    <strong>5.</strong> Better Bundle services will resume
                    immediately
                  </Text>
                </BlockStack>
              </BlockStack>
            </div>
          </Card>

          {/* Need Help */}
          <Card>
            <div style={{ padding: "20px" }}>
              <BlockStack gap="300">
                <div
                  style={{
                    padding: "16px",
                    backgroundColor: "#FEF3C7",
                    borderRadius: "12px",
                    border: "1px solid #FCD34D",
                  }}
                >
                  <div style={{ color: "#92400E" }}>
                    <Text as="h3" variant="headingMd" fontWeight="bold">
                      💡 Need Help?
                    </Text>
                  </div>
                </div>
                <BlockStack gap="200">
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Who can approve?</strong> Only store owners and
                    admins with billing permissions can approve subscriptions.
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Already approved?</strong> Click "Check Approval
                    Status" above. Changes may take a few moments to reflect.
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    <strong>Wrong spending cap?</strong> Cancel this
                    subscription and start the setup process again with your
                    desired monthly cap amount.
                  </Text>
                </BlockStack>
              </BlockStack>
            </div>
          </Card>
        </div>

        {/* Cancel Section */}
        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="300">
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <Text as="h3" variant="headingMd" fontWeight="semibold">
                    Cancel Pending Subscription
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Changed your mind or need to adjust your spending cap? You
                    can cancel this pending subscription and set it up again.
                  </Text>
                </BlockStack>
                <Button
                  variant="primary"
                  tone="critical"
                  onClick={handleCancelSubscription}
                  loading={isLoading}
                >
                  Open Shopify to Cancel
                </Button>
              </InlineStack>
            </BlockStack>
          </div>
        </Card>
      </BlockStack>
    </BillingLayout>
  );
}
