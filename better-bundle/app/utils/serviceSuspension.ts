import prisma from "app/db.server";

interface SuspensionStatus {
  isSuspended: boolean;
  reason: string;
  requiresBillingSetup: boolean;
  trialCompleted: boolean;
  subscriptionActive: boolean;
  suspensionDetails?: {
    suspendedAt: string;
    suspensionReason: string;
    serviceImpact: string;
  };
}

/**
 * Check if shop services should be suspended
 */
export async function checkServiceSuspension(
  shopId: string,
): Promise<SuspensionStatus> {
  try {
    // Get shop and billing plan
    const shop = await prisma.shops.findUnique({
      where: { id: shopId },
      select: {
        id: true,
        is_active: true,
        suspended_at: true,
        suspension_reason: true,
        service_impact: true,
      },
    });

    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shopId,
        status: "active",
      },
      select: {
        is_trial_active: true,
        configuration: true,
        trial_revenue: true,
        trial_threshold: true,
      },
    });

    if (!shop || !billingPlan) {
      return {
        isSuspended: true,
        reason: "shop_or_billing_plan_not_found",
        requiresBillingSetup: false,
        trialCompleted: false,
        subscriptionActive: false,
      };
    }

    // Check if shop is already suspended
    if (!shop.is_active || shop.suspended_at) {
      return {
        isSuspended: true,
        reason: shop.suspension_reason || "manually_suspended",
        requiresBillingSetup: false,
        trialCompleted: false,
        subscriptionActive: false,
        suspensionDetails: {
          suspendedAt:
            shop.suspended_at?.toISOString() || new Date().toISOString(),
          suspensionReason: shop.suspension_reason || "manually_suspended",
          serviceImpact: shop.service_impact || "suspended",
        },
      };
    }

    const config = billingPlan.configuration as any;
    const trialCompleted =
      !billingPlan.is_trial_active && config?.trial_completed_at;
    const subscriptionActive =
      config?.subscription_id && config?.subscription_status === "ACTIVE";
    const requiresBillingSetup =
      config?.subscription_required && !config?.subscription_id;

    // Check if trial completed but billing not set up
    if (trialCompleted && requiresBillingSetup && !subscriptionActive) {
      return {
        isSuspended: true,
        reason: "trial_completed_billing_required",
        requiresBillingSetup: true,
        trialCompleted: true,
        subscriptionActive: false,
      };
    }

    // Check if subscription is pending approval
    if (
      trialCompleted &&
      config?.subscription_id &&
      config?.subscription_status === "PENDING"
    ) {
      return {
        isSuspended: true,
        reason: "subscription_pending_approval",
        requiresBillingSetup: false,
        trialCompleted: true,
        subscriptionActive: false,
      };
    }

    // Check if subscription was declined
    if (
      trialCompleted &&
      config?.subscription_id &&
      config?.subscription_status === "DECLINED"
    ) {
      return {
        isSuspended: true,
        reason: "subscription_declined",
        requiresBillingSetup: true,
        trialCompleted: true,
        subscriptionActive: false,
      };
    }

    // Services are active
    return {
      isSuspended: false,
      reason: "active",
      requiresBillingSetup: false,
      trialCompleted: trialCompleted,
      subscriptionActive: subscriptionActive,
    };
  } catch (error) {
    console.error("Error checking service suspension:", error);
    return {
      isSuspended: true,
      reason: "error_checking_status",
      requiresBillingSetup: false,
      trialCompleted: false,
      subscriptionActive: false,
    };
  }
}

/**
 * Suspend shop services
 */
export async function suspendShopServices(
  shopId: string,
  reason: string = "trial_completed_consent_required",
  serviceImpact: string = "suspended",
): Promise<boolean> {
  try {
    console.log(`🔄 Suspending services for shop ${shopId}: ${reason}`);

    // Update shop status
    await prisma.shops.update({
      where: { id: shopId },
      data: {
        is_active: false,
        suspended_at: new Date(),
        suspension_reason: reason,
        service_impact: serviceImpact,
        updated_at: new Date(),
      },
    });

    // Update billing plan configuration
    await prisma.billing_plans.updateMany({
      where: {
        shop_id: shopId,
        status: "active",
      },
      data: {
        configuration: {
          services_stopped: true,
          suspension_reason: reason,
          suspended_at: new Date().toISOString(),
          service_impact: serviceImpact,
        },
      },
    });

    // Create billing event
    await prisma.billing_events.create({
      data: {
        shop_id: shopId,
        plan_id: "", // Will be updated with actual plan ID if needed
        type: "services_suspended",
        data: {
          reason: reason,
          suspended_at: new Date().toISOString(),
          service_impact: serviceImpact,
        },
        billing_metadata: {
          suspension_type: "automatic",
          reason: reason,
        },
        occurred_at: new Date(),
        processed_at: new Date(),
        created_at: new Date(),
      },
    });

    console.log(`✅ Services suspended for shop ${shopId}`);
    return true;
  } catch (error) {
    console.error(`❌ Error suspending services for shop ${shopId}:`, error);
    return false;
  }
}

/**
 * Reactivate shop services
 */
export async function reactivateShopServices(shopId: string): Promise<boolean> {
  try {
    console.log(`🔄 Reactivating services for shop ${shopId}`);

    // Update shop status
    await prisma.shops.update({
      where: { id: shopId },
      data: {
        is_active: true,
        suspended_at: null,
        suspension_reason: null,
        service_impact: "active",
        updated_at: new Date(),
      },
    });

    // Update billing plan configuration
    await prisma.billing_plans.updateMany({
      where: {
        shop_id: shopId,
        status: "active",
      },
      data: {
        configuration: {
          services_stopped: false,
          suspension_reason: null,
          suspended_at: null,
          service_impact: "active",
        },
      },
    });

    // Create billing event
    await prisma.billing_events.create({
      data: {
        shop_id: shopId,
        plan_id: "", // Will be updated with actual plan ID if needed
        type: "services_reactivated",
        data: {
          reactivated_at: new Date().toISOString(),
          service_impact: "active",
        },
        billing_metadata: {
          reactivation_type: "automatic",
        },
        occurred_at: new Date(),
        processed_at: new Date(),
        created_at: new Date(),
      },
    });

    console.log(`✅ Services reactivated for shop ${shopId}`);
    return true;
  } catch (error) {
    console.error(`❌ Error reactivating services for shop ${shopId}:`, error);
    return false;
  }
}

/**
 * Check if shop should be suspended and suspend if needed
 */
export async function checkAndSuspendIfNeeded(shopId: string): Promise<{
  wasSuspended: boolean;
  suspensionStatus: SuspensionStatus;
}> {
  const suspensionStatus = await checkServiceSuspension(shopId);

  if (suspensionStatus.isSuspended && suspensionStatus.requiresBillingSetup) {
    const suspended = await suspendShopServices(
      shopId,
      "trial_completed_billing_required",
      "suspended",
    );

    return {
      wasSuspended: suspended,
      suspensionStatus,
    };
  }

  return {
    wasSuspended: false,
    suspensionStatus,
  };
}

/**
 * Get suspension message for UI
 */
export function getSuspensionMessage(suspensionStatus: SuspensionStatus): {
  title: string;
  message: string;
  actionRequired: boolean;
  actionText?: string;
  actionUrl?: string;
} {
  if (!suspensionStatus.isSuspended) {
    return {
      title: "Services Active",
      message: "All Better Bundle services are running normally.",
      actionRequired: false,
    };
  }

  switch (suspensionStatus.reason) {
    case "trial_completed_billing_required":
      return {
        title: "Billing Setup Required",
        message:
          "Your trial has completed. Please set up billing to continue using Better Bundle.",
        actionRequired: true,
        actionText: "Setup Billing",
        actionUrl: "/app/billing",
      };

    case "subscription_pending_approval":
      return {
        title: "Subscription Pending",
        message:
          "Your billing subscription is pending approval. Services will resume once approved.",
        actionRequired: false,
      };

    case "subscription_declined":
      return {
        title: "Subscription Declined",
        message:
          "Your billing subscription was declined. Please set up billing again to continue.",
        actionRequired: true,
        actionText: "Setup Billing",
        actionUrl: "/app/billing",
      };

    case "manually_suspended":
      return {
        title: "Services Suspended",
        message:
          "Your services have been manually suspended. Please contact support.",
        actionRequired: true,
        actionText: "Contact Support",
        actionUrl: "/app/help",
      };

    default:
      return {
        title: "Services Suspended",
        message:
          "Your services are currently suspended. Please contact support for assistance.",
        actionRequired: true,
        actionText: "Contact Support",
        actionUrl: "/app/help",
      };
  }
}
