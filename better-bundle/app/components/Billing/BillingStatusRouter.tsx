import { TrialActive } from "./TrialActive";

interface BillingStatusRouterProps {
  shopCurrency: string;
  trialPlanData: any;
}

export function BillingStatusRouter({
  trialPlanData,
  shopCurrency,
}: BillingStatusRouterProps) {
  if (trialPlanData && trialPlanData.isTrialActive) {
    return (
      <TrialActive shopCurrency={shopCurrency} trialPlanData={trialPlanData} />
    );
  }
  return null;
}
