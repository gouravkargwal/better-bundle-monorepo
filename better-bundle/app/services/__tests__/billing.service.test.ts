import { describe, it, expect, vi, beforeEach } from "vitest";

// ── Hoisted mocks ──────────────────────────────────────────────────────────

const { mockPrisma, mockInvalidateCache } = vi.hoisted(() => ({
  mockPrisma: {
    shop_subscriptions: {
      findFirst: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
    },
    shops: {
      findUnique: vi.fn(),
      update: vi.fn(),
    },
    commission_records: { aggregate: vi.fn(), findMany: vi.fn() },
    billing_cycles: { findFirst: vi.fn(), create: vi.fn(), update: vi.fn() },
    subscription_plans: { findFirst: vi.fn() },
    pricing_tiers: { findFirst: vi.fn() },
  },
  mockInvalidateCache: vi.fn(),
}));

vi.mock("../../db.server", () => ({ default: mockPrisma }));
vi.mock("../../utils/logger", () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock("../../middleware/serviceSuspension", () => ({
  invalidateSuspensionCache: mockInvalidateCache,
}));

import {
  createShopSubscription,
  activateSubscription,
  reactivateShopIfSuspended,
} from "../billing.service";

// ── Helpers ────────────────────────────────────────────────────────────────

function defaultPlan() {
  return { id: "plan-1", name: "Default", is_active: true, is_default: true };
}

function defaultTier() {
  return {
    id: "tier-1",
    subscription_plan_id: "plan-1",
    currency: "USD",
    is_active: true,
    is_default: true,
    monthly_fee: 29,
    trial_days: 14,
  };
}

function defaultSubscription(overrides: any = {}) {
  return {
    id: "sub-1",
    shop_id: "shop-1",
    subscription_type: "TRIAL",
    status: "TRIAL",
    is_active: true,
    pricing_tier_id: "tier-1",
    monthly_fee_override: null,
    trial_duration_days: null,
    pricing_tiers: defaultTier(),
    ...overrides,
  };
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("billing.service (root)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  // ─── createShopSubscription ────────────────────────────────────────────

  describe("createShopSubscription", () => {
    it("creates trial subscription with default plan and pricing tier", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null); // No existing
      mockPrisma.subscription_plans.findFirst.mockResolvedValue(defaultPlan());
      mockPrisma.pricing_tiers.findFirst.mockResolvedValue(defaultTier());
      mockPrisma.shop_subscriptions.create.mockResolvedValue({
        id: "sub-new",
        subscription_type: "TRIAL",
        status: "TRIAL",
      });

      const result = await createShopSubscription("shop-1", "test.myshopify.com");

      expect(mockPrisma.shop_subscriptions.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          shop_id: "shop-1",
          subscription_plan_id: "plan-1",
          pricing_tier_id: "tier-1",
          subscription_type: "TRIAL",
          status: "TRIAL",
          is_active: true,
          auto_renew: true,
          trial_duration_days: 14, // flat fee: trial_days from pricing tier
        }),
      });
      expect(result.shop_subscription.id).toBe("sub-new");
    });

    it("returns existing subscription if one already exists (idempotent)", async () => {
      const existing = defaultSubscription();
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(existing);

      const result = await createShopSubscription("shop-1", "test.myshopify.com");

      expect(result.shop_subscription).toBe(existing);
      expect(mockPrisma.shop_subscriptions.create).not.toHaveBeenCalled();
    });

    it("throws when no default subscription plan found", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null);
      mockPrisma.subscription_plans.findFirst.mockResolvedValue(null);

      await expect(
        createShopSubscription("shop-1", "test.myshopify.com"),
      ).rejects.toThrow("No default subscription plan found");
    });

    it("throws when no default pricing tier found", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null);
      mockPrisma.subscription_plans.findFirst.mockResolvedValue(defaultPlan());
      mockPrisma.pricing_tiers.findFirst.mockResolvedValue(null);

      await expect(
        createShopSubscription("shop-1", "test.myshopify.com"),
      ).rejects.toThrow("No default pricing tier found");
    });
  });

  // ─── activateSubscription ──────────────────────────────────────────────

  describe("activateSubscription", () => {
    it("activates subscription with flat fee, creates billing cycle, reactivates shop", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        defaultSubscription(),
      );
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});
      mockPrisma.billing_cycles.create.mockResolvedValue({
        id: "cycle-1",
        cycle_number: 1,
      });
      // reactivateShopIfSuspended mocks
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        shop_domain: "test.myshopify.com",
        is_active: false,
      });
      mockPrisma.shops.update.mockResolvedValue({});
      mockInvalidateCache.mockResolvedValue(undefined);

      const result = await activateSubscription(
        "shop-1",
        "gid://shopify/AppSubscription/123",
      );

      // Verify subscription updated to PAID/ACTIVE
      expect(mockPrisma.shop_subscriptions.update).toHaveBeenCalledWith({
        where: { id: "sub-1" },
        data: expect.objectContaining({
          shopify_subscription_id: "gid://shopify/AppSubscription/123",
          shopify_status: "ACTIVE",
          subscription_type: "PAID",
          status: "ACTIVE",
        }),
      });

      // Verify billing cycle created with period_fee
      expect(mockPrisma.billing_cycles.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          shop_subscription_id: "sub-1",
          cycle_number: 1,
          period_fee: 29, // flat fee from pricing tier
          status: "ACTIVE",
        }),
      });

      expect(result.success).toBe(true);
    });

    it("throws when no subscription found", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null);

      await expect(
        activateSubscription("shop-1", "gid://shopify/AppSubscription/123"),
      ).rejects.toThrow("Shop subscription not found");
    });
  });

  // ─── reactivateShopIfSuspended ─────────────────────────────────────────

  describe("reactivateShopIfSuspended", () => {
    it("reactivates suspended shop and invalidates cache", async () => {
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        shop_domain: "test.myshopify.com",
        is_active: false,
      });
      mockPrisma.shops.update.mockResolvedValue({});
      mockInvalidateCache.mockResolvedValue(undefined);

      await reactivateShopIfSuspended("shop-1");

      expect(mockPrisma.shops.update).toHaveBeenCalledWith({
        where: { id: "shop-1" },
        data: expect.objectContaining({
          is_active: true,
          suspended_at: null,
          suspension_reason: null,
          service_impact: null,
        }),
      });
      expect(mockInvalidateCache).toHaveBeenCalledWith("shop-1");
    });

    it("does nothing if shop is already active", async () => {
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        is_active: true,
      });

      await reactivateShopIfSuspended("shop-1");

      expect(mockPrisma.shops.update).not.toHaveBeenCalled();
      expect(mockInvalidateCache).not.toHaveBeenCalled();
    });

    it("does nothing if shop not found", async () => {
      mockPrisma.shops.findUnique.mockResolvedValue(null);

      await reactivateShopIfSuspended("shop-1");

      expect(mockPrisma.shops.update).not.toHaveBeenCalled();
    });
  });
});
