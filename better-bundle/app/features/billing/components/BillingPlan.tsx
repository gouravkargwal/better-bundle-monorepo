import { BlockStack, Button, Card, InlineStack, Text } from "@shopify/polaris";
import type { BillingState, BillingSetupData } from "../types/billing.types";
import { TrialActive } from "./TrialActive";
import { TrialCompleted } from "./TrialCompleted";
import { SubscriptionActive } from "./SubscriptionActive";
import { SubscriptionSuspended } from "./SubscriptionSuspended";

interface BillingPlanProps {
  shopId: string;
  shopCurrency: string;
  billingState: BillingState;
}

export function BillingPlan({
  shopId,
  shopCurrency,
  billingState,
}: BillingPlanProps) {
  if (!billingState) {
    return (
      <Card>
        <div style={{ padding: "24px", textAlign: "center" }}>
          <Text as="p">No billing information available</Text>
        </div>
      </Card>
    );
  }

  // Route to appropriate component based on billing status
  const renderBillingComponent = () => {
    switch (billingState.status) {
      case "trial_active":
        return (
          <TrialActive
            trialData={billingState.trialData}
            shopCurrency={shopCurrency}
          />
        );

      case "trial_completed":
        return (
          <TrialCompleted
            trialData={billingState.trialData!}
            shopCurrency={shopCurrency}
            onSetupBilling={async (setupData: BillingSetupData) => {
              // The commission rate is read server-side from the plan so the
              // client cannot choose its own price. The cap is the merchant's
              // own spending limit, so their choice is passed along — the
              // server still clamps it to the range we allow.
              const response = await fetch("/api/billing/setup", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  planName: setupData.planName,
                  cappedAmount: setupData.cappedAmount,
                }),
              });

              const result = await response.json();
              if (result.success && result.confirmationUrl) {
                window.top!.location.href = result.confirmationUrl;
              } else {
                console.error("No confirmation URL in response:", result);
              }
              return result;
            }}
          />
        );

      case "subscription_active":
        return (
          <SubscriptionActive
            subscriptionData={billingState.subscriptionData!}
            shopCurrency={shopCurrency}
          />
        );

      case "subscription_suspended":
        return (
          <SubscriptionSuspended
            subscriptionData={billingState.subscriptionData!}
            shopCurrency={shopCurrency}
            onReactivate={async () => {
              window.location.href = "/app/billing?action=reactivate";
              return { success: true };
            }}
          />
        );

      // Reachable whenever the merchant cancels in their Shopify admin. It
      // used to fall through to the default and print the raw status string.
      case "subscription_cancelled":
        return (
          <Card>
            <BlockStack gap="300">
              <Text variant="headingMd" as="h3">
                Subscription cancelled
              </Text>
              <Text as="p" tone="subdued">
                Recommendations have stopped showing and you will not be
                charged again. Your data is still here. There is no in-app way
                to resubscribe yet — get in touch and we'll switch it back on.
              </Text>
              <InlineStack>
                <Button url="/app/help">Contact support</Button>
              </InlineStack>
            </BlockStack>
          </Card>
        );

      default:
        return (
          <Card>
            <div style={{ padding: "24px", textAlign: "center" }}>
              <Text as="p">
                We can't load your billing details right now. Please refresh, or
                contact support if this keeps happening.
              </Text>
            </div>
          </Card>
        );
    }
  };

  return renderBillingComponent();
}
