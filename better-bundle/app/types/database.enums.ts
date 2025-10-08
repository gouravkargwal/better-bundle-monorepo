/**
 * Database enum values that match the Prisma schema
 * These enums ensure consistency between TypeScript and database
 */

export enum SubscriptionStatus {
  TRIAL = "trial",
  PENDING_APPROVAL = "pending_approval",
  TRIAL_COMPLETED = "trial_completed",
  ACTIVE = "active",
  SUSPENDED = "suspended",
  CANCELLED = "cancelled",
  EXPIRED = "expired",
}

export enum CommissionStatus {
  TRIAL_PENDING = "trial_pending",
  TRIAL_COMPLETED = "trial_completed",
  PENDING = "pending",
  RECORDED = "recorded",
  INVOICED = "invoiced",
  REJECTED = "rejected",
  FAILED = "failed",
  CAPPED = "capped",
}

export enum ChargeType {
  FULL = "full",
  PARTIAL = "partial",
  OVERFLOW_ONLY = "overflow_only",
  TRIAL = "trial",
  REJECTED = "rejected",
}

export enum BillingPhase {
  TRIAL = "trial",
  PAID = "paid",
}

export enum TrialStatus {
  ACTIVE = "active",
  COMPLETED = "completed",
  EXPIRED = "expired",
}

export enum ShopifySubscriptionStatus {
  PENDING = "pending",
  ACTIVE = "active",
  DECLINED = "declined",
  CANCELLED = "cancelled",
  EXPIRED = "expired",
}

export enum AdjustmentReason {
  CAP_INCREASE = "cap_increase",
  PLAN_UPGRADE = "plan_upgrade",
  ADMIN_ADJUSTMENT = "admin_adjustment",
  PROMOTION = "promotion",
  DISPUTE_RESOLUTION = "dispute_resolution",
}
