import { Page, Card, Text } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import type { BillingState } from "../types/billing.types";
import { TrialActive } from "./TrialActive";
import { SubscriptionPending } from "./SubscriptionPending";
import { SubscriptionActive } from "./SubscriptionActive";
import { SubscriptionSuspended } from "./SubscriptionSuspended";

interface BillingPageProps {
  shopId: string;
  shopCurrency: string;
  billingState: BillingState;
}

async function setupBilling() {
  const response = await fetch("/api/billing/setup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });

  const result = await response.json();
  if (result.success && result.confirmationUrl) {
    window.top!.location.href = result.confirmationUrl;
  } else {
    console.error("No confirmation URL in response:", result);
  }
  return result;
}

export function BillingPage({
  shopId,
  shopCurrency,
  billingState,
}: BillingPageProps) {
  if (!billingState) {
    return (
      <Page>
        <TitleBar title="Billing" />
        <Card>
          <div style={{ padding: "24px", textAlign: "center" }}>
            <Text as="p">No billing information available</Text>
          </div>
        </Card>
      </Page>
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
            onSetupBilling={setupBilling}
          />
        );

      case "subscription_pending":
        return (
          <SubscriptionPending
            subscriptionData={billingState.subscriptionData!}
            shopCurrency={shopCurrency}
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
              // This would typically redirect to a reactivation flow
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

  return (
    <Page>
      <TitleBar title="Billing" />
      {renderBillingComponent()}
    </Page>
  );
}
