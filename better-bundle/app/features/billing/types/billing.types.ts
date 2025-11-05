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
}

export interface SubscriptionData {
  id: string;
  status: "PENDING" | "ACTIVE" | "DECLINED" | "CANCELLED" | "EXPIRED";
  spendingLimit: number;
  currentUsage: number; // Total: shopifyUsage + expectedCharge
  shopifyUsage: number; // What's actually recorded to Shopify (RECORDED commissions)
  expectedCharge: number; // Pending commissions not yet recorded (PENDING status only, excluding REJECTED)
  rejectedAmount?: number; // Optional: Show rejected commissions separately for transparency
  usagePercentage: number;
  confirmationUrl?: string;
  currency: string;
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
