import { TrialActive } from "./TrialActive";
import { BillingSetup } from "./BillingSetup";
import { SubscriptionPending } from "./SubscriptionPending";
import { SubscriptionActive } from "./SubscriptionActive";
import { useBillingActions } from "../../hooks/useBillingActions";

interface BillingStatusRouterProps {
  shopCurrency: string;
  trialPlanData: any;
  billingPlan?: any;
}

export function BillingStatusRouter({
  trialPlanData,
  shopCurrency,
  billingPlan,
}: BillingStatusRouterProps) {
  const {
    spendingLimit,
    setSpendingLimit,
    handleSetupBilling,
    handleCancelSubscription,
    isLoading,
  } = useBillingActions(shopCurrency);

  console.log(billingPlan, "------------------>");

  // Trial is active - show trial progress
  if (trialPlanData && trialPlanData.isTrialActive) {
    return (
      <TrialActive shopCurrency={shopCurrency} trialPlanData={trialPlanData} />
    );
  }

  // Trial completed but no subscription yet - show setup billing
  if (
    (billingPlan && billingPlan.status === "suspended") ||
    billingPlan.subscription_status === "DECLINED"
  ) {
    return (
      <BillingSetup
        billingPlan={billingPlan}
        spendingLimit={spendingLimit}
        setSpendingLimit={setSpendingLimit}
        onSetupBilling={handleSetupBilling}
        isLoading={isLoading}
        shopCurrency={shopCurrency}
      />
    );
  }

  // Subscription is pending approval - show pending state
  if (
    billingPlan &&
    billingPlan.status === "pending" &&
    billingPlan.subscription_status === "PENDING"
  ) {
    return (
      <SubscriptionPending
        billingPlan={billingPlan}
        isLoading={isLoading}
        handleCancelSubscription={handleCancelSubscription}
      />
    );
  }

  // Subscription is active - show active state with usage data
  // This handles both normal active state and cap reached state
  if (
    billingPlan &&
    billingPlan.status === "active" &&
    billingPlan.subscription_status === "ACTIVE"
  ) {
    return (
      <SubscriptionActive
        billingPlan={billingPlan}
        shopCurrency={shopCurrency}
      />
    );
  }

  return null;
}
