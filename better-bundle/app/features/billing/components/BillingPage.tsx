import { Page, Card, Text } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import type { BillingState, BillingSetupData } from "../types/billing.types";
import { TrialActive } from "./TrialActive";
import { TrialCompleted } from "./TrialCompleted";
import { SubscriptionPending } from "./SubscriptionPending";
import { SubscriptionActive } from "./SubscriptionActive";
import { SubscriptionSuspended } from "./SubscriptionSuspended";

interface BillingPageProps {
  shopId: string;
  shopCurrency: string;
  billingState: BillingState;
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
          />
        );

      case "trial_completed":
        return (
          <TrialCompleted
            trialData={billingState.trialData!}
            shopCurrency={shopCurrency}
            onSetupBilling={async (setupData: BillingSetupData) => {
              try {
                // Use planId to set up recurring billing
                const response = await fetch("/api/billing/setup", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    planId: setupData.planId,
                    currency: setupData.currency,
                  }),
                });

                if (!response.ok) {
                  throw new Error(
                    `HTTP ${response.status}: ${response.statusText}`,
                  );
                }

                const result = await response.json();

                if (result.success && result.confirmationUrl) {
                  window.top!.location.href = result.confirmationUrl;
                } else {
                  throw new Error(
                    result.error || "No confirmation URL in response",
                  );
                }
                return result;
              } catch (error) {
                console.error("Billing setup failed:", error);
                throw error;
              }
            }}
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
            onIncreaseCap={async () => {
              // Flat fee pricing — no cap to increase
              return { success: false, error: "Not applicable for flat fee plans" };
            }}
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

  return (
    <Page>
      <TitleBar title="Billing" />
      {renderBillingComponent()}
    </Page>
  );
}
