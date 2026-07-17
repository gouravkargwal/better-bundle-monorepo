/**
 * Billing feature types
 * Flat-fee subscription: single monthly price, time-based free trial.
 */

export interface BillingState {
  status: BillingStatus;
  trialData?: TrialData;
  subscriptionData?: SubscriptionData;
  error?: BillingError;
}

export type BillingStatus =
  | "trial_active"
  | "subscription_pending"
  | "subscription_active"
  | "subscription_suspended"
  | "subscription_cancelled";

export interface TrialData {
  isActive: boolean;
  trialDays: number;
  daysRemaining?: number;
  monthlyPrice: number;
  currency: string;
}

export interface SubscriptionData {
  id: string;
  status: "PENDING" | "ACTIVE" | "DECLINED" | "CANCELLED" | "EXPIRED";
  monthlyPrice: number;
  currency: string;
  confirmationUrl?: string;
}

export interface BillingError {
  code: string;
  message: string;
  actionRequired?: boolean;
  actionUrl?: string;
}
