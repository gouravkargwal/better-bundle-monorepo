/**
 * Database enum values that match the Prisma schema
 * These enums ensure consistency between TypeScript and database
 */

export enum SubscriptionStatus {
  TRIAL = "trial",
  ACTIVE = "active",
  SUSPENDED = "suspended",
  CANCELLED = "cancelled",
  EXPIRED = "expired",
}

// CommissionStatus, ChargeType, and BillingPhase enums removed — migrated to flat-rate billing
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
