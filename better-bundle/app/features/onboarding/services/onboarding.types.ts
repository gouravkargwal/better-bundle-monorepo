// features/onboarding/services/onboarding.types.ts
export interface OnboardingData {
  pricingTier: {
    symbol: string;
    threshold_amount: number;
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
