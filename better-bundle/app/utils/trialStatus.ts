/**
 * Trial Status Utility
 *
 * Implements industry-standard trial tracking for Pattern 1: Value-First Approach
 * Based on successful patterns from Klaviyo, ReCharge, Bold Apps, and other industry leaders
 */

import prisma from "../db.server";

export interface TrialStatus {
  isTrialActive: boolean;
  trialCompleted: boolean;
  needsConsent: boolean;
  currentRevenue: number;
  threshold: number;
  remainingRevenue: number;
  progress: number;
  currency: string;
}

export async function getTrialStatus(shopId: string): Promise<TrialStatus> {
  try {
    // Get billing plan for the shop
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shopId,
        status: "active",
        is_trial_active: true,
      },
    });

    if (!billingPlan) {
      // No trial plan found - check if they have a paid plan
      await prisma.billing_plans.findFirst({
        where: {
          shop_id: shopId,
          status: "active",
          is_trial_active: false,
        },
      });

      return {
        isTrialActive: false,
        trialCompleted: true,
        needsConsent: false,
        currentRevenue: 0,
        threshold: 0,
        remainingRevenue: 0,
        progress: 100,
        currency: "UNKNOWN",
      };
    }

    // Get current attributed revenue for this period
    const currentRevenue = billingPlan.trial_revenue || 0;
    const threshold = billingPlan.trial_threshold || 0;
    const currency = billingPlan.configuration?.currency;

    if (!currency) {
      throw new Error("No currency configured for billing plan");
    }

    // Check if trial is still active
    const isTrialActive = currentRevenue < threshold;
    const trialCompleted = !isTrialActive;

    // Check if consent is needed (trial completed but no subscription created)
    const needsConsent =
      trialCompleted && !billingPlan.configuration?.subscription_created;

    // Calculate remaining revenue and progress
    const remainingRevenue = Math.max(0, threshold - currentRevenue);
    const progress = Math.min(100, (currentRevenue / threshold) * 100);

    return {
      isTrialActive,
      trialCompleted,
      needsConsent,
      currentRevenue,
      threshold,
      remainingRevenue,
      progress,
      currency,
    };
  } catch (error) {
    console.error("Error getting trial status:", error);
    return {
      isTrialActive: false,
      trialCompleted: false,
      needsConsent: false,
      currentRevenue: 0,
      threshold: 0,
      remainingRevenue: 0,
      progress: 0,
      currency: "UNKNOWN",
    };
  }
}

export async function updateTrialRevenue(
  shopId: string,
  additionalRevenue: number,
): Promise<boolean> {
  try {
    // Update trial revenue
    await prisma.billing_plans.updateMany({
      where: {
        shop_id: shopId,
        status: "active",
        is_trial_active: true,
      },
      data: {
        trial_revenue: {
          increment: additionalRevenue,
        },
      },
    });

    // Check if trial should be completed
    const trialStatus = await getTrialStatus(shopId);

    if (trialStatus.trialCompleted && !trialStatus.needsConsent) {
      // Trial completed and subscription already created
      await prisma.billing_plans.updateMany({
        where: {
          shop_id: shopId,
          status: "active",
          is_trial_active: true,
        },
        data: {
          is_trial_active: false,
        },
      });
    }

    return true;
  } catch (error) {
    console.error("Error updating trial revenue:", error);
    return false;
  }
}

export async function createTrialPlan(
  shopId: string,
  shopDomain: string,
  currency: string = "USD",
): Promise<boolean> {
  try {
    // Check if trial plan already exists
    const existingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shopId,
        status: "active",
      },
    });

    if (existingPlan) {
      return true; // Plan already exists
    }

    // Create trial plan without subscription
    await prisma.billing_plans.create({
      data: {
        shop_id: shopId,
        shop_domain: shopDomain,
        name: "Free Trial Plan",
        type: "trial_only",
        status: "active",
        configuration: {
          trial_active: true,
          trial_threshold: 0.0,
          trial_revenue: 0.0,
          revenue_share_rate: 0.03,
          currency: currency,
          subscription_required: false,
          trial_without_consent: true,
        },
        effective_from: new Date(),
        is_trial_active: true,
        trial_threshold: 0.0,
        trial_revenue: 0.0,
      },
    });

    return true;
  } catch (error) {
    console.error("Error creating trial plan:", error);
    return false;
  }
}

export async function completeTrialWithConsent(
  shopId: string,
): Promise<boolean> {
  try {
    // Update billing plan to mark trial as completed
    await prisma.billing_plans.updateMany({
      where: {
        shop_id: shopId,
        status: "active",
        is_trial_active: true,
      },
      data: {
        is_trial_active: false,
        configuration: {
          trial_active: false,
          trial_completed_at: new Date().toISOString(),
          consent_given: true,
          subscription_required: true,
        },
      },
    });

    // Create billing event
    await prisma.billing_events.create({
      data: {
        shop_id: shopId,
        type: "trial_completed_with_consent",
        data: {
          completed_at: new Date().toISOString(),
          consent_given: true,
        },
        metadata: {
          event_type: "trial_completion",
          consent_given: true,
        },
      },
    });

    return true;
  } catch (error) {
    console.error("Error completing trial with consent:", error);
    return false;
  }
}
