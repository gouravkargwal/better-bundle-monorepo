/**
 * Trial Status Testing Suite
 *
 * Tests the $200 revenue-based trial flow with comprehensive scenarios
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  getTrialStatus,
  updateTrialRevenue,
  createTrialPlan,
  completeTrialWithConsent,
} from "../trialStatus";
import prisma from "../../db.server";

// Mock Prisma
vi.mock("../../db.server", () => ({
  default: {
    billingPlan: {
      findFirst: vi.fn(),
      create: vi.fn(),
      updateMany: vi.fn(),
    },
    billingEvent: {
      create: vi.fn(),
    },
  },
}));

describe("Trial Status Flow", () => {
  const mockShopId = "test-shop.myshopify.com";
  const mockShopDomain = "test-shop.myshopify.com";

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Trial Creation", () => {
    it("should create trial plan with $200 threshold", async () => {
      // Mock no existing plan
      (prisma.billingPlan.findFirst as any).mockResolvedValue(null);
      (prisma.billingPlan.create as any).mockResolvedValue({ id: "plan-123" });

      const result = await createTrialPlan(mockShopId, mockShopDomain, "USD");

      expect(result).toBe(true);
      expect(prisma.billingPlan.create).toHaveBeenCalledWith({
        data: {
          shopId: mockShopId,
          shopDomain: mockShopDomain,
          name: "Free Trial Plan",
          type: "trial_only",
          status: "active",
          configuration: {
            trial_active: true,
            trial_threshold: 200.0,
            trial_revenue: 0.0,
            revenue_share_rate: 0.03,
            currency: "USD",
            subscription_required: false,
            trial_without_consent: true,
          },
          effectiveFrom: expect.any(Date),
          isTrialActive: true,
          trialThreshold: 200.0,
          trialRevenue: 0.0,
        },
      });
    });

    it("should not create duplicate trial plan", async () => {
      // Mock existing plan
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        id: "existing-plan",
      });

      const result = await createTrialPlan(mockShopId, mockShopDomain, "USD");

      expect(result).toBe(true);
      expect(prisma.billingPlan.create).not.toHaveBeenCalled();
    });
  });

  describe("Trial Status Tracking", () => {
    it("should show active trial with $0 revenue", async () => {
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 0,
        trialThreshold: 200,
        configuration: { currency: "USD" },
      });

      const status = await getTrialStatus(mockShopId);

      expect(status).toEqual({
        isTrialActive: true,
        trialCompleted: false,
        needsConsent: false,
        currentRevenue: 0,
        threshold: 200,
        remainingRevenue: 200,
        progress: 0,
        currency: "USD",
      });
    });

    it("should show active trial with $150 revenue (75% complete)", async () => {
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 150,
        trialThreshold: 200,
        configuration: { currency: "USD" },
      });

      const status = await getTrialStatus(mockShopId);

      expect(status).toEqual({
        isTrialActive: true,
        trialCompleted: false,
        needsConsent: false,
        currentRevenue: 150,
        threshold: 200,
        remainingRevenue: 50,
        progress: 75,
        currency: "USD",
      });
    });

    it("should show completed trial with $200+ revenue", async () => {
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 250,
        trialThreshold: 200,
        configuration: { currency: "USD" },
      });

      const status = await getTrialStatus(mockShopId);

      expect(status).toEqual({
        isTrialActive: false,
        trialCompleted: true,
        needsConsent: true,
        currentRevenue: 250,
        threshold: 200,
        remainingRevenue: 0,
        progress: 100,
        currency: "USD",
      });
    });

    it("should show completed trial with subscription created", async () => {
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 250,
        trialThreshold: 200,
        configuration: {
          currency: "USD",
          subscription_created: true,
        },
      });

      const status = await getTrialStatus(mockShopId);

      expect(status).toEqual({
        isTrialActive: false,
        trialCompleted: true,
        needsConsent: false, // No consent needed - subscription exists
        currentRevenue: 250,
        threshold: 200,
        remainingRevenue: 0,
        progress: 100,
        currency: "USD",
      });
    });
  });

  describe("Revenue Updates", () => {
    it("should update trial revenue and keep trial active", async () => {
      (prisma.billingPlan.updateMany as any).mockResolvedValue({ count: 1 });
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 150,
        trialThreshold: 200,
        configuration: { currency: "USD" },
      });

      const result = await updateTrialRevenue(mockShopId, 50);

      expect(result).toBe(true);
      expect(prisma.billingPlan.updateMany).toHaveBeenCalledWith({
        where: {
          shopId: mockShopId,
          status: "active",
          isTrialActive: true,
        },
        data: {
          trialRevenue: { increment: 50 },
        },
      });
    });

    it("should complete trial when threshold reached", async () => {
      (prisma.billingPlan.updateMany as any).mockResolvedValue({ count: 1 });
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 200,
        trialThreshold: 200,
        configuration: { currency: "USD" },
      });

      const result = await updateTrialRevenue(mockShopId, 50);

      expect(result).toBe(true);
      // Should mark trial as inactive
      expect(prisma.billingPlan.updateMany).toHaveBeenCalledWith({
        where: {
          shopId: mockShopId,
          status: "active",
          isTrialActive: true,
        },
        data: {
          isTrialActive: false,
        },
      });
    });
  });

  describe("Trial Completion with Consent", () => {
    it("should complete trial and create billing event", async () => {
      (prisma.billingPlan.updateMany as any).mockResolvedValue({ count: 1 });
      (prisma.billingEvent.create as any).mockResolvedValue({
        id: "event-123",
      });

      const result = await completeTrialWithConsent(mockShopId);

      expect(result).toBe(true);
      expect(prisma.billingPlan.updateMany).toHaveBeenCalledWith({
        where: {
          shopId: mockShopId,
          status: "active",
          isTrialActive: true,
        },
        data: {
          isTrialActive: false,
          configuration: {
            trial_active: false,
            trial_completed_at: expect.any(String),
            consent_given: true,
            subscription_required: true,
          },
        },
      });
      expect(prisma.billingEvent.create).toHaveBeenCalledWith({
        data: {
          shopId: mockShopId,
          type: "trial_completed_with_consent",
          data: {
            completed_at: expect.any(String),
            consent_given: true,
          },
          metadata: {
            event_type: "trial_completion",
            consent_given: true,
          },
        },
      });
    });
  });

  describe("Edge Cases", () => {
    it("should handle missing billing plan", async () => {
      (prisma.billingPlan.findFirst as any).mockResolvedValue(null);

      const status = await getTrialStatus(mockShopId);

      expect(status).toEqual({
        isTrialActive: false,
        trialCompleted: true,
        needsConsent: false,
        currentRevenue: 0,
        threshold: 200,
        remainingRevenue: 0,
        progress: 100,
        currency: "USD",
      });
    });

    it("should handle database errors gracefully", async () => {
      (prisma.billingPlan.findFirst as any).mockRejectedValue(
        new Error("Database error"),
      );

      const status = await getTrialStatus(mockShopId);

      expect(status).toEqual({
        isTrialActive: false,
        trialCompleted: false,
        needsConsent: false,
        currentRevenue: 0,
        threshold: 200,
        remainingRevenue: 200,
        progress: 0,
        currency: "USD",
      });
    });
  });
});
