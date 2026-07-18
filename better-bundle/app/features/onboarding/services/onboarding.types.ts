// features/onboarding/services/onboarding.types.ts
export interface OnboardingData {
  subscriptionPlan: {
    symbol: string;
    monthly_fee: number;
    trial_days: number;
    plan_name: string;
  } | null;
}

export interface OnboardingError {
  error: string;
}

export interface ShopData {
  id: string;
  name: string;
  myshopifyDomain: string;
  primaryDomain: {
    host: string;
    url: string;
  };
  email: string;
  currencyCode: string;
  plan: {
    displayName: string;
  };
}
