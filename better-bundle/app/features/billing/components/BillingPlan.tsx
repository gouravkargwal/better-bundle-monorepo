import { Card, Text } from "@shopify/polaris";
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
              // Only the plan name is sent. Rate and cap are read server-side
              // from the plan so the client cannot choose its own price.
              const response = await fetch("/api/billing/setup", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ planName: setupData.planName }),
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

      default:
        return (
          <Card>
            <div style={{ padding: "24px", textAlign: "center" }}>
              <Text as="p">Unknown billing status: {billingState.status}</Text>
            </div>
          </Card>
        );
    }
  };

  return renderBillingComponent();
}
