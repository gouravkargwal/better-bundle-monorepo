/**
 * Billing feature types
 * Simplified state management for billing flow
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
  | "subscription_pending"
  | "subscription_active"
  | "subscription_suspended"
  | "subscription_cancelled";

export interface TrialData {
  isActive: boolean;
  thresholdAmount: number;
  accumulatedRevenue: number;
  progress: number; // 0-100
  daysRemaining?: number;
  currency: string;
  commissionRate: number; // e.g. 0.03 for 3%
}

export interface SubscriptionData {
  id: string;
  status: "PENDING" | "ACTIVE" | "DECLINED" | "CANCELLED" | "EXPIRED";
  spendingLimit: number;
  /**
   * Current usage sourced from billing_cycles.usage_amount (single source of truth,
   * maintained by the Python worker via update_billing_cycle_usage).
   * This reflects what's been recorded to Shopify — no longer recomputed by the Remix app.
   */
  currentUsage: number;
  /** Shopify GraphQL balanceUsed — for transparency in the breakdown */
  shopifyUsage: number;
  /**
   * Always 0. Previously recomputed from PENDING commission records in the Remix app,
   * duplicating the Python worker's logic. Now usage_amount is the single source of truth.
   */
  expectedCharge: number;
  /** Optional: Show rejected commissions separately for transparency */
  rejectedAmount?: number;
  usagePercentage: number;
  confirmationUrl?: string;
  currency: string;
  commissionRate: number; // e.g. 0.03 for 3%
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
  spendingLimit: number;
  currency: string;
}

export interface BillingMetrics {
  totalRevenue: number;
  attributedRevenue: number;
  commissionEarned: number;
  commissionRate: number;
  currency: string;
}
