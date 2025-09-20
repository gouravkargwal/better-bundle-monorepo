/**
 * Trial Flow Integration Tests
 *
 * Tests the complete $200 trial flow from start to finish
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  getTrialStatus,
  updateTrialRevenue,
  createTrialPlan,
  completeTrialWithConsent,
} from "../trialStatus";
import prisma from "../../db.server";

// Mock Prisma with realistic data
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

describe("Complete Trial Flow Integration", () => {
  const mockShopId = "test-shop.myshopify.com";
  const mockShopDomain = "test-shop.myshopify.com";

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Scenario 1: Successful Trial Completion", () => {
    it("should complete full trial flow: $0 → $150 → $200+ → consent", async () => {
      // Step 1: Create trial plan
      (prisma.billingPlan.findFirst as any).mockResolvedValue(null);
      (prisma.billingPlan.create as any).mockResolvedValue({ id: "plan-123" });

      const createResult = await createTrialPlan(
        mockShopId,
        mockShopDomain,
        "USD",
      );
      expect(createResult).toBe(true);

      // Step 2: Check initial status ($0 revenue)
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 0,
        trialThreshold: 200,
        configuration: { currency: "USD" },
      });

      let status = await getTrialStatus(mockShopId);
      expect(status.isTrialActive).toBe(true);
      expect(status.currentRevenue).toBe(0);
      expect(status.remainingRevenue).toBe(200);
      expect(status.progress).toBe(0);

      // Step 3: Update revenue to $150 (75% complete)
      (prisma.billingPlan.updateMany as any).mockResolvedValue({ count: 1 });
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 150,
        trialThreshold: 200,
        configuration: { currency: "USD" },
      });

      const updateResult1 = await updateTrialRevenue(mockShopId, 150);
      expect(updateResult1).toBe(true);

      status = await getTrialStatus(mockShopId);
      expect(status.isTrialActive).toBe(true);
      expect(status.currentRevenue).toBe(150);
      expect(status.remainingRevenue).toBe(50);
      expect(status.progress).toBe(75);

      // Step 4: Update revenue to $200+ (trial complete)
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 200,
        trialThreshold: 200,
        configuration: { currency: "USD" },
      });

      const updateResult2 = await updateTrialRevenue(mockShopId, 50);
      expect(updateResult2).toBe(true);

      status = await getTrialStatus(mockShopId);
      expect(status.isTrialActive).toBe(false);
      expect(status.trialCompleted).toBe(true);
      expect(status.needsConsent).toBe(true);
      expect(status.currentRevenue).toBe(200);
      expect(status.remainingRevenue).toBe(0);
      expect(status.progress).toBe(100);

      // Step 5: Complete trial with consent
      (prisma.billingPlan.updateMany as any).mockResolvedValue({ count: 1 });
      (prisma.billingEvent.create as any).mockResolvedValue({
        id: "event-123",
      });

      const consentResult = await completeTrialWithConsent(mockShopId);
      expect(consentResult).toBe(true);

      // Step 6: Verify final status
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 200,
        trialThreshold: 200,
        configuration: {
          currency: "USD",
          subscription_created: true,
        },
      });

      status = await getTrialStatus(mockShopId);
      expect(status.isTrialActive).toBe(false);
      expect(status.trialCompleted).toBe(true);
      expect(status.needsConsent).toBe(false); // Subscription created
    });
  });

  describe("Scenario 2: Trial with Multiple Revenue Updates", () => {
    it("should handle incremental revenue updates", async () => {
      // Mock trial plan
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 0,
        trialThreshold: 200,
        configuration: { currency: "USD" },
      });

      // Simulate multiple revenue updates
      const revenueUpdates = [25, 50, 75, 100, 150, 200];
      let cumulativeRevenue = 0;

      for (const update of revenueUpdates) {
        cumulativeRevenue += update;

        (prisma.billingPlan.updateMany as any).mockResolvedValue({ count: 1 });
        (prisma.billingPlan.findFirst as any).mockResolvedValue({
          trialRevenue: cumulativeRevenue,
          trialThreshold: 200,
          configuration: { currency: "USD" },
        });

        const result = await updateTrialRevenue(mockShopId, update);
        expect(result).toBe(true);

        const status = await getTrialStatus(mockShopId);

        if (cumulativeRevenue < 200) {
          expect(status.isTrialActive).toBe(true);
          expect(status.remainingRevenue).toBe(200 - cumulativeRevenue);
          expect(status.progress).toBe((cumulativeRevenue / 200) * 100);
        } else {
          expect(status.isTrialActive).toBe(false);
          expect(status.trialCompleted).toBe(true);
          expect(status.needsConsent).toBe(true);
        }
      }
    });
  });

  describe("Scenario 3: Trial with Different Currencies", () => {
    it("should handle trial with EUR currency", async () => {
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 150,
        trialThreshold: 200,
        configuration: { currency: "EUR" },
      });

      const status = await getTrialStatus(mockShopId);

      expect(status.currency).toBe("EUR");
      expect(status.isTrialActive).toBe(true);
      expect(status.currentRevenue).toBe(150);
      expect(status.remainingRevenue).toBe(50);
    });

    it("should handle trial with GBP currency", async () => {
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 180,
        trialThreshold: 200,
        configuration: { currency: "GBP" },
      });

      const status = await getTrialStatus(mockShopId);

      expect(status.currency).toBe("GBP");
      expect(status.isTrialActive).toBe(true);
      expect(status.currentRevenue).toBe(180);
      expect(status.remainingRevenue).toBe(20);
    });
  });

  describe("Scenario 4: Error Handling", () => {
    it("should handle database connection errors", async () => {
      (prisma.billingPlan.findFirst as any).mockRejectedValue(
        new Error("Connection failed"),
      );

      const status = await getTrialStatus(mockShopId);

      // Should return safe defaults
      expect(status.isTrialActive).toBe(false);
      expect(status.trialCompleted).toBe(false);
      expect(status.needsConsent).toBe(false);
    });

    it("should handle partial revenue update failures", async () => {
      (prisma.billingPlan.updateMany as any).mockRejectedValue(
        new Error("Update failed"),
      );

      const result = await updateTrialRevenue(mockShopId, 50);

      expect(result).toBe(false);
    });
  });

  describe("Scenario 5: Edge Cases", () => {
    it("should handle exact threshold amount", async () => {
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 200,
        trialThreshold: 200,
        configuration: { currency: "USD" },
      });

      const status = await getTrialStatus(mockShopId);

      expect(status.isTrialActive).toBe(false);
      expect(status.trialCompleted).toBe(true);
      expect(status.needsConsent).toBe(true);
      expect(status.progress).toBe(100);
    });

    it("should handle revenue exceeding threshold", async () => {
      (prisma.billingPlan.findFirst as any).mockResolvedValue({
        trialRevenue: 250,
        trialThreshold: 200,
        configuration: { currency: "USD" },
      });

      const status = await getTrialStatus(mockShopId);

      expect(status.isTrialActive).toBe(false);
      expect(status.trialCompleted).toBe(true);
      expect(status.needsConsent).toBe(true);
      expect(status.progress).toBe(100);
    });
  });
});
