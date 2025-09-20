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
    const billingPlan = await prisma.billingPlan.findFirst({
      where: {
        shopId: shopId,
        status: "active",
        isTrialActive: true,
      },
    });

    if (!billingPlan) {
      // No trial plan found - check if they have a paid plan
      const paidPlan = await prisma.billingPlan.findFirst({
        where: {
          shopId: shopId,
          status: "active",
          isTrialActive: false,
        },
      });

      return {
        isTrialActive: false,
        trialCompleted: true,
        needsConsent: false,
        currentRevenue: 0,
        threshold: 200,
        remainingRevenue: 0,
        progress: 100,
        currency: "USD",
      };
    }

    // Get current attributed revenue for this period
    const currentRevenue = billingPlan.trialRevenue || 0;
    const threshold = billingPlan.trialThreshold || 200;
    const currency = billingPlan.configuration?.currency || "USD";

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
      threshold: 200,
      remainingRevenue: 200,
      progress: 0,
      currency: "USD",
    };
  }
}

export async function updateTrialRevenue(
  shopId: string,
  additionalRevenue: number,
): Promise<boolean> {
  try {
    // Update trial revenue
    await prisma.billingPlan.updateMany({
      where: {
        shopId: shopId,
        status: "active",
        isTrialActive: true,
      },
      data: {
        trialRevenue: {
          increment: additionalRevenue,
        },
      },
    });

    // Check if trial should be completed
    const trialStatus = await getTrialStatus(shopId);

    if (trialStatus.trialCompleted && !trialStatus.needsConsent) {
      // Trial completed and subscription already created
      await prisma.billingPlan.updateMany({
        where: {
          shopId: shopId,
          status: "active",
          isTrialActive: true,
        },
        data: {
          isTrialActive: false,
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
    const existingPlan = await prisma.billingPlan.findFirst({
      where: {
        shopId: shopId,
        status: "active",
      },
    });

    if (existingPlan) {
      return true; // Plan already exists
    }

    // Create trial plan without subscription
    await prisma.billingPlan.create({
      data: {
        shopId: shopId,
        shopDomain: shopDomain,
        name: "Free Trial Plan",
        type: "trial_only",
        status: "active",
        configuration: {
          trial_active: true,
          trial_threshold: 200.0,
          trial_revenue: 0.0,
          revenue_share_rate: 0.03,
          currency: currency,
          subscription_required: false,
          trial_without_consent: true,
        },
        effectiveFrom: new Date(),
        isTrialActive: true,
        trialThreshold: 200.0,
        trialRevenue: 0.0,
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
    await prisma.billingPlan.updateMany({
      where: {
        shopId: shopId,
        status: "active",
        isTrialActive: true,
      },
      data: {
        isTrialActive: false,
        configuration: {
          trial_active: false,
          trial_completed_at: new Date().toISOString(),
          consent_given: true,
          subscription_required: true,
        },
      },
    });

    // Create billing event
    await prisma.billingEvent.create({
      data: {
        shopId: shopId,
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
