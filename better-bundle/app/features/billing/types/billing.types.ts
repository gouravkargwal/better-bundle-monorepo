/**
 * Billing feature types
 *
 * Pay-as-you-go: the shop is charged `commissionRate` of the revenue attributed
 * to recommendations, never more than `cappedAmount` in a 30-day cycle. The
 * trial ends when attributed revenue reaches `trialThreshold`. There is no
 * elapsed-time gate: a shop that has not been sold that much has not received
 * what it was promised.
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
  /** Attributed revenue earned so far during the trial. */
  revenueEarned: number;
  /** Attributed revenue the shop gets free before the first charge. */
  trialThreshold: number;
  /** The terms that take effect once the trial ends, for the copy. */
  commissionRate: number;
  cappedAmount: number;
  currency: string;
}

export interface SubscriptionData {
  id: string;
  status: "PENDING" | "ACTIVE" | "DECLINED" | "CANCELLED" | "EXPIRED";
  planName: string;
  /** Share of attributed revenue charged, e.g. 0.03 for 3%. */
  commissionRate: number;
  /** Maximum chargeable per 30-day cycle — what the merchant approved. */
  cappedAmount: number;
  /** Charged so far in the current cycle. */
  usageThisCycle: number;
  /** Attributed revenue in the current cycle, which usage is derived from. */
  attributedThisCycle: number;
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

/**
 * What the client sends to start billing — the plan name and nothing else.
 * Rate and cap are read from the plan server-side; accepting them from the
 * browser would let a merchant name their own price.
 */
export interface BillingSetupData {
  planName: string;
}
