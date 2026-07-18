/**
 * Billing feature types
 * Flat fee pricing types for subscription management
 */

export interface BillingState {
  status: BillingStatus;
  trialData?: TrialData;
  subscriptionData?: SubscriptionData;
  error?: BillingError;
}

export type BillingStatus =
  | "trial_active"
  | "trial_completed"
  | "trial_expired"
  | "subscription_pending"
  | "subscription_active"
  | "subscription_suspended"
  | "subscription_cancelled";

export interface TrialData {
  isActive: boolean;
  daysRemaining: number;
  trialDays: number; // Total trial days (e.g., 14)
  currency: string;
}

export interface SubscriptionData {
  id: string;
  status: "PENDING" | "ACTIVE" | "DECLINED" | "CANCELLED" | "EXPIRED";
  planName: string;
  monthlyFee: number;
  currency: string;
  confirmationUrl?: string;
  billingCycle?: {
    startDate: string;
    endDate: string;
    cycleNumber: number;
  };
}

export interface BillingError {
  code: string;
  message: string;
  actionRequired?: boolean;
  actionUrl?: string;
}

export interface BillingSetupData {
  planName: string;
  monthlyFee: number;
  trialDays: number;
}

export interface BillingMetrics {
  totalRevenue: number;
  attributedRevenue: number;
  currency: string;
}
