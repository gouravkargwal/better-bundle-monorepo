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
    console.log(billingState.status);

    switch (billingState.status) {
      case "trial_active":
        return (
          <TrialActive
            trialData={billingState.trialData!}
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
                // This will be handled by the existing API route
                const response = await fetch("/api/billing/setup", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    monthlyCap: setupData.spendingLimit,
                    currency: setupData.currency,
                  }),
                });

                if (!response.ok) {
                  throw new Error(
                    `HTTP ${response.status}: ${response.statusText}`,
                  );
                }

                const result = await response.json();
                console.log("Billing setup response:", result);

                if (result.success && result.confirmationUrl) {
                  console.log("Redirecting to:", result.confirmationUrl);
                  window.top!.location.href = result.confirmationUrl;
                } else {
                  throw new Error(
                    result.error || "No confirmation URL in response",
                  );
                }
                return result;
              } catch (error) {
                console.error("Billing setup failed:", error);
                throw error; // Re-throw to let component handle it
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
            onIncreaseCap={async (newLimit: number) => {
              const response = await fetch("/api/billing/increase-cap", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ spendingLimit: newLimit }),
              });

              const result = await response.json();
              if (result.success) {
                window.location.reload();
              }
              return result;
            }}
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
