import { TrialActive } from "./TrialActive";
import { SubscriptionCancelled } from "./SubscriptionCancelled";
import { SubscriptionPending } from "./SubscriptionPending";
import { SubscriptionActive } from "./SubscriptionActive";

interface BillingStatusRouterProps {
  billingPlan: any;
  billingActions: {
    isLoading: boolean;
    spendingLimit: string;
    setSpendingLimit: (value: string) => void;
    handleSetupBilling: () => void;
    handleCancelSubscription: () => void;
    formatCurrency: (amount: number, currency?: string) => string;
  };
}

export function BillingStatusRouter({
  billingPlan,
  billingActions,
}: BillingStatusRouterProps) {
  // Debug logging
  console.log("🔍 Billing Status Router:", {
    subscription_status: billingPlan.subscription_status,
    is_trial_active: billingPlan.is_trial_active,
    subscription_id: billingPlan.subscription_id,
  });

  // ============= TRIAL ACTIVE =============
  // Check if trial is active based on revenue vs threshold
  const isTrialActive =
    billingPlan.is_trial_active ||
    (billingPlan.attributed_revenue < billingPlan.trial_threshold &&
      billingPlan.subscription_status !== "ACTIVE");

  if (isTrialActive) {
    return (
      <TrialActive
        billingPlan={billingPlan}
        formatCurrency={billingActions.formatCurrency}
      />
    );
  }

  // ============= TRIAL COMPLETED - SUBSCRIPTION REQUIRED =============
  // If trial completed but subscription not active yet
  if (
    billingPlan.attributed_revenue >= billingPlan.trial_threshold &&
    billingPlan.subscription_status !== "ACTIVE" &&
    billingPlan.subscription_status !== "CANCELLED"
  ) {
    return (
      <SubscriptionPending
        billingPlan={billingPlan}
        handleCancelSubscription={billingActions.handleCancelSubscription}
        isLoading={billingActions.isLoading}
      />
    );
  }

  // ============= SUBSCRIPTION CANCELLED =============
  if (
    billingPlan.subscription_status === "CANCELLED" ||
    billingPlan.subscription_status === "CANCELLED_BY_MERCHANT"
  ) {
    return (
      <SubscriptionCancelled
        spendingLimit={billingActions.spendingLimit}
        setSpendingLimit={billingActions.setSpendingLimit}
        handleSetupBilling={billingActions.handleSetupBilling}
        isLoading={billingActions.isLoading}
      />
    );
  }

  // ============= SUBSCRIPTION PENDING =============
  if (billingPlan.subscription_status === "PENDING") {
    return (
      <SubscriptionPending
        billingPlan={billingPlan}
        handleCancelSubscription={billingActions.handleCancelSubscription}
        isLoading={billingActions.isLoading}
      />
    );
  }

  // ============= SUBSCRIPTION ACTIVE =============
  if (billingPlan.subscription_status === "ACTIVE") {
    return (
      <SubscriptionActive
        billingPlan={billingPlan}
        formatCurrency={billingActions.formatCurrency}
        handleCancelSubscription={billingActions.handleCancelSubscription}
        isLoading={billingActions.isLoading}
      />
    );
  }

  // ============= FALLBACK =============
  return (
    <div>
      <h2>Unknown Status</h2>
      <p>Status: {billingPlan.subscription_status}</p>
    </div>
  );
}
