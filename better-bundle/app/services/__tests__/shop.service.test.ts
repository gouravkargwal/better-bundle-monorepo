import { describe, it, expect, vi, beforeEach } from "vitest";

// ── Hoisted mocks ──────────────────────────────────────────────────────────

const { mockPrisma } = vi.hoisted(() => ({
  mockPrisma: {
    shops: {
      findUnique: vi.fn(),
      update: vi.fn(),
    },
    shop_subscriptions: {
      findFirst: vi.fn(),
      updateMany: vi.fn(),
    },
  },
}));

vi.mock("../../db.server", () => ({ default: mockPrisma }));
vi.mock("../../utils/logger", () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

import {
  getShop,
  getShopOnboardingCompleted,
  getShopifyPlusStatus,
  getShopSubscription,
  deactivateShopBilling,
} from "../shop.service";

// ── Helpers ────────────────────────────────────────────────────────────────

function defaultShopRecord() {
  return {
    id: "shop-1",
    shop_domain: "test.myshopify.com",
    access_token: "shpat_test",
    currency_code: "USD",
    email: "test@test.com",
    plan_type: "Basic",
    is_active: true,
    onboarding_completed: true,
    shopify_plus: false,
  };
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("shop.service", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  // ─── getShop ───────────────────────────────────────────────────────────

  describe("getShop", () => {
    it("returns shop by domain", async () => {
      const shop = defaultShopRecord();
      mockPrisma.shops.findUnique.mockResolvedValue(shop);

      const result = await getShop("test.myshopify.com");

      expect(result).toBe(shop);
      expect(mockPrisma.shops.findUnique).toHaveBeenCalledWith({
        where: { shop_domain: "test.myshopify.com" },
      });
    });

    it("returns null when shop not found", async () => {
      mockPrisma.shops.findUnique.mockResolvedValue(null);

      const result = await getShop("nonexistent.myshopify.com");

      expect(result).toBeNull();
    });

    it("returns null on database error", async () => {
      mockPrisma.shops.findUnique.mockRejectedValue(new Error("DB error"));

      const result = await getShop("test.myshopify.com");

      expect(result).toBeNull();
    });
  });

  // ─── getShopOnboardingCompleted ────────────────────────────────────────

  describe("getShopOnboardingCompleted", () => {
    it("returns true when onboarding is completed", async () => {
      mockPrisma.shops.findUnique.mockResolvedValue({
        ...defaultShopRecord(),
        onboarding_completed: true,
      });

      const result = await getShopOnboardingCompleted("test.myshopify.com");

      expect(result).toBe(true);
    });

    it("returns false when onboarding is not completed", async () => {
      mockPrisma.shops.findUnique.mockResolvedValue({
        ...defaultShopRecord(),
        onboarding_completed: false,
      });

      const result = await getShopOnboardingCompleted("test.myshopify.com");

      expect(result).toBe(false);
    });

    it("returns false when shop not found", async () => {
      mockPrisma.shops.findUnique.mockResolvedValue(null);

      const result = await getShopOnboardingCompleted("test.myshopify.com");

      expect(result).toBe(false);
    });

    it("returns false on error", async () => {
      mockPrisma.shops.findUnique.mockRejectedValue(new Error("DB error"));

      const result = await getShopOnboardingCompleted("test.myshopify.com");

      expect(result).toBe(false);
    });
  });

  // ─── getShopifyPlusStatus ──────────────────────────────────────────────

  describe("getShopifyPlusStatus", () => {
    it("returns true for Shopify Plus shops", async () => {
      mockPrisma.shops.findUnique.mockResolvedValue({
        shopify_plus: true,
        plan_type: "Shopify Plus",
      });

      const result = await getShopifyPlusStatus("test.myshopify.com");

      expect(result).toBe(true);
    });

    it("returns false for non-Plus shops", async () => {
      mockPrisma.shops.findUnique.mockResolvedValue({
        shopify_plus: false,
        plan_type: "Basic",
      });

      const result = await getShopifyPlusStatus("test.myshopify.com");

      expect(result).toBe(false);
    });

    it("returns false when shop not found", async () => {
      mockPrisma.shops.findUnique.mockResolvedValue(null);

      const result = await getShopifyPlusStatus("test.myshopify.com");

      expect(result).toBe(false);
    });
  });

  // ─── deactivateShopBilling ─────────────────────────────────────────────

  describe("deactivateShopBilling", () => {
    it("marks shop inactive and cancels all active subscriptions", async () => {
      mockPrisma.shops.update.mockResolvedValue({ id: "shop-1" });
      mockPrisma.shop_subscriptions.updateMany.mockResolvedValue({ count: 1 });

      const result = await deactivateShopBilling("test.myshopify.com");

      // Shop marked inactive
      expect(mockPrisma.shops.update).toHaveBeenCalledWith({
        where: { shop_domain: "test.myshopify.com" },
        data: expect.objectContaining({
          is_active: false,
        }),
      });

      // Subscriptions cancelled (all non-terminal statuses)
      expect(mockPrisma.shop_subscriptions.updateMany).toHaveBeenCalledWith({
        where: {
          shop_id: "shop-1",
          status: { in: ["ACTIVE", "TRIAL", "PENDING_APPROVAL", "SUSPENDED"] },
        },
        data: expect.objectContaining({
          status: "CANCELLED",
        }),
      });

      expect(result.success).toBe(true);
      expect(result.plans_deactivated_count).toBe(1);
      expect(result.reason).toBe("app_uninstalled");
    });

    it("accepts custom reason parameter", async () => {
      mockPrisma.shops.update.mockResolvedValue({ id: "shop-1" });
      mockPrisma.shop_subscriptions.updateMany.mockResolvedValue({ count: 0 });

      const result = await deactivateShopBilling(
        "test.myshopify.com",
        "manual_deactivation",
      );

      expect(result.reason).toBe("manual_deactivation");
    });

    it("throws on database error", async () => {
      mockPrisma.shops.update.mockRejectedValue(new Error("DB error"));

      await expect(
        deactivateShopBilling("test.myshopify.com"),
      ).rejects.toThrow("Failed to deactivate billing for shop");
    });
  });

  // ─── getShopSubscription ───────────────────────────────────────────────

  describe("getShopSubscription", () => {
    it("returns active billing plan for shop", async () => {
      mockPrisma.shops.findUnique.mockResolvedValue({ id: "shop-1" });
      const plan = { id: "sub-1", shop_id: "shop-1", status: "ACTIVE" };
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(plan);

      const result = await getShopSubscription("test.myshopify.com");

      expect(result).toBe(plan);
    });

    it("returns null when shop not found", async () => {
      mockPrisma.shops.findUnique.mockResolvedValue(null);

      const result = await getShopSubscription("test.myshopify.com");

      expect(result).toBeNull();
    });

    it("returns null when no active subscription", async () => {
      mockPrisma.shops.findUnique.mockResolvedValue({ id: "shop-1" });
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null);

      const result = await getShopSubscription("test.myshopify.com");

      expect(result).toBeNull();
    });
  });
});
