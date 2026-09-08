// features/onboarding/services/onboarding.types.ts
export interface OnboardingData {
  subscriptionPlan: {
    symbol: string;
    /** Share of attributed revenue charged, e.g. 0.03 for 3%. */
    commission_rate: number;
    /** Maximum chargeable per 30-day cycle. */
    cap_amount: number;
    /** Attributed revenue earned free before the first charge. */
    trial_revenue_threshold: number;
    plan_name: string;
  } | null;
}

export interface OnboardingError {
  error: string;
}
