import { BillingSetup } from "./BillingSetup";
import { TrialActive } from "./TrialActive";
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
  };
  billing: any;
}

export function BillingStatusRouter({
  billingPlan,
  billingActions,
  billing,
}: BillingStatusRouterProps) {
  console.log(billingPlan, "------------------>");

  const trialRevenue =
    (billingPlan as any)?.trial_revenue ??
    (billingPlan as any)?.attributed_revenue ??
    0;
  const trialThreshold = (billingPlan as any)?.trial_threshold ?? 0;
  const isTrialActive =
    billingPlan.is_trial_active && trialRevenue < trialThreshold;

  if (isTrialActive) {
    return <TrialActive billingPlan={billingPlan} />;
  }

  if (billingPlan.subscription_status === "ACTIVE") {
    return <SubscriptionActive billingPlan={billingPlan} />;
  }

  if (
    billingPlan.subscription_id &&
    billingPlan.subscription_status === "PENDING"
  ) {
    return (
      <SubscriptionPending
        billingPlan={billingPlan}
        isLoading={billingActions.isLoading}
        handleCancelSubscription={billingActions.handleCancelSubscription}
      />
    );
  }

  const isTrialCompleted = !billingPlan.is_trial_active;

  const noSubscriptionCreated =
    !billingPlan.subscription_id ||
    billingPlan.subscription_status === "none" ||
    billingPlan.subscription_status === null ||
    billingPlan.subscription_status === "CANCELLED" ||
    billingPlan.subscription_status === "CANCELLED_BY_MERCHANT" ||
    billingPlan.subscription_status === "DECLINED";

  if (isTrialCompleted && noSubscriptionCreated) {
    return (
      <BillingSetup
        billingPlan={billingPlan}
        spendingLimit={billingActions.spendingLimit}
        setSpendingLimit={billingActions.setSpendingLimit}
        onSetupBilling={billingActions.handleSetupBilling}
        isLoading={billingActions.isLoading}
      />
    );
  }

  return (
    <div style={{ padding: "24px" }}>
      <h2>Unknown Billing Status</h2>
      <p>
        <strong>Status:</strong> {billingPlan.subscription_status || "none"}
      </p>
      <p>
        <strong>Trial Active:</strong>{" "}
        {billingPlan.is_trial_active ? "Yes" : "No"}
      </p>
      <p>
        <strong>Subscription ID:</strong>{" "}
        {billingPlan.subscription_id || "none"}
      </p>
      <p>Please contact support if you see this message.</p>
    </div>
  );
}
