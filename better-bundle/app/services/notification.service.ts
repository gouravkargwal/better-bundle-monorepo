import type { SuspensionStatus } from "../middleware/serviceSuspension";

export interface NotificationMessage {
  id: string;
  type: "warning" | "critical" | "info" | "success";
  title: string;
  message: string;
  action?: { label: string; url: string };
}

/**
 * Generate billing-related notifications from the shop's suspension status.
 * These are shown as in-app notification banners at the top of the app layout.
 */
export function getBillingNotifications(
  suspensionStatus: SuspensionStatus | null,
): NotificationMessage[] {
  const notifications: NotificationMessage[] = [];

  if (!suspensionStatus) return notifications;

  // ── Payment failure ───────────────────────────────────────────
  if (
    suspensionStatus.isSuspended &&
    suspensionStatus.reason === "payment_failure"
  ) {
    notifications.push({
      id: "payment_failure",
      type: "critical",
      title: "Payment Failed",
      message:
        "Your latest payment failed. Please update your billing information to avoid service interruption.",
      action: { label: "Update Billing", url: "/app/billing" },
    });
  }

  // ── Generic suspension (not payment failure) ─────────────────
  if (
    suspensionStatus.isSuspended &&
    suspensionStatus.reason &&
    suspensionStatus.reason !== "payment_failure" &&
    suspensionStatus.reason !== "trial_completed_awaiting_setup" &&
    suspensionStatus.reason !== "subscription_pending_approval"
  ) {
    notifications.push({
      id: "subscription_suspended",
      type: "critical",
      title: "Subscription Suspended",
      message: `Your subscription has been suspended: ${suspensionStatus.reason}. Please reactivate to continue using the app.`,
      action: { label: "Reactivate", url: "/app/billing" },
    });
  }

  // ── Billing setup required ──────────────────────────────────
  if (suspensionStatus.requiresBillingSetup) {
    notifications.push({
      id: "requires_billing_setup",
      type: "warning",
      title: "Billing Setup Required",
      message:
        "Please set up your billing information to continue using the app.",
      action: { label: "Setup Billing", url: "/app/billing" },
    });
  }

  // ── Trial completed (awaiting subscription) ─────────────────
  if (
    suspensionStatus.trialCompleted &&
    !suspensionStatus.subscriptionActive &&
    !suspensionStatus.isSuspended
  ) {
    notifications.push({
      id: "trial_completed",
      type: "warning",
      title: "Trial Ended",
      message:
        "Your free trial has ended. Choose a plan to continue using Better Bundle.",
      action: { label: "View Plans", url: "/app/billing" },
    });
  }



  return notifications;
}
