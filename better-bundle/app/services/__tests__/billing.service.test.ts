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
  completeTrialAndCreateCycle,
  activateSubscription,
  increaseBillingCycleCap,
  reactivateShopIfSuspended,
  getTrialRevenueData,
  getUsageRevenueData,
  getCurrentCycleMetrics,
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
    trial_threshold_amount: 75,
    commission_rate: 0.03,
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
    user_chosen_cap_amount: 100,
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
          user_chosen_cap_amount: 75, // trial_threshold_amount
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

  // ─── completeTrialAndCreateCycle ───────────────────────────────────────

  describe("completeTrialAndCreateCycle", () => {
    it("updates subscription status to PENDING_APPROVAL", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        defaultSubscription(),
      );
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});

      const result = await completeTrialAndCreateCycle("shop-1");

      expect(mockPrisma.shop_subscriptions.update).toHaveBeenCalledWith({
        where: { id: "sub-1" },
        data: { status: "PENDING_APPROVAL" },
      });
      expect(result.success).toBe(true);
    });

    it("throws when no active subscription found", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null);

      await expect(completeTrialAndCreateCycle("shop-1")).rejects.toThrow(
        "Shop subscription not found",
      );
    });
  });

  // ─── activateSubscription ──────────────────────────────────────────────

  describe("activateSubscription", () => {
    it("activates subscription, creates first billing cycle, reactivates shop", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        defaultSubscription({ user_chosen_cap_amount: 200 }),
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
        is_active: false, // Suspended
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

      // Verify billing cycle created with user's chosen cap
      expect(mockPrisma.billing_cycles.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          shop_subscription_id: "sub-1",
          cycle_number: 1,
          initial_cap_amount: 200,
          current_cap_amount: 200,
          usage_amount: 0,
          commission_count: 0,
          status: "ACTIVE",
        }),
      });

      // Verify shop reactivated
      expect(mockPrisma.shops.update).toHaveBeenCalled();
      expect(result.success).toBe(true);
    });

    it("uses fallback cap of 1000 when user_chosen_cap_amount is null", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        defaultSubscription({ user_chosen_cap_amount: null }),
      );
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});
      mockPrisma.billing_cycles.create.mockResolvedValue({ id: "cycle-1" });
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        is_active: true,
      });

      await activateSubscription("shop-1", "gid://shopify/AppSubscription/123");

      expect(mockPrisma.billing_cycles.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          initial_cap_amount: 1000,
          current_cap_amount: 1000,
        }),
      });
    });

    it("throws when no subscription found", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null);

      await expect(
        activateSubscription("shop-1", "gid://shopify/AppSubscription/123"),
      ).rejects.toThrow("Shop subscription not found");
    });
  });

  // ─── increaseBillingCycleCap ───────────────────────────────────────────

  describe("increaseBillingCycleCap", () => {
    it("updates current billing cycle cap amount", async () => {
      mockPrisma.billing_cycles.findFirst.mockResolvedValue({
        id: "cycle-1",
        current_cap_amount: 100,
      });
      mockPrisma.billing_cycles.update.mockResolvedValue({});

      const result = await increaseBillingCycleCap("shop-1", 250);

      expect(mockPrisma.billing_cycles.update).toHaveBeenCalledWith({
        where: { id: "cycle-1" },
        data: { current_cap_amount: 250 },
      });
      expect(result.message).toContain("100");
      expect(result.message).toContain("250");
    });

    it("throws when no active billing cycle found", async () => {
      mockPrisma.billing_cycles.findFirst.mockResolvedValue(null);

      await expect(
        increaseBillingCycleCap("shop-1", 250),
      ).rejects.toThrow("No active billing cycle found");
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

  // ─── getTrialRevenueData ───────────────────────────────────────────────

  describe("getTrialRevenueData", () => {
    it("returns trial revenue and commission from commission records", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        defaultSubscription(),
      );
      mockPrisma.commission_records.aggregate.mockResolvedValue({
        _sum: { attributed_revenue: 500 },
      });

      const result = await getTrialRevenueData("shop-1");

      expect(result.attributedRevenue).toBe(500);
      expect(result.commissionEarned).toBe(15); // 500 * 0.03
    });

    it("returns zeros when no trial subscription exists", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null);

      const result = await getTrialRevenueData("shop-1");

      expect(result.attributedRevenue).toBe(0);
      expect(result.commissionEarned).toBe(0);
    });

    it("returns zeros when subscription is not TRIAL type", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        defaultSubscription({ subscription_type: "PAID" }),
      );

      const result = await getTrialRevenueData("shop-1");

      expect(result.attributedRevenue).toBe(0);
      expect(result.commissionEarned).toBe(0);
    });

    it("handles null aggregate sum (no records)", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        defaultSubscription(),
      );
      mockPrisma.commission_records.aggregate.mockResolvedValue({
        _sum: { attributed_revenue: null },
      });

      const result = await getTrialRevenueData("shop-1");

      expect(result.attributedRevenue).toBe(0);
      expect(result.commissionEarned).toBe(0);
    });
  });

  // ─── getUsageRevenueData ───────────────────────────────────────────────

  describe("getUsageRevenueData", () => {
    it("returns usage revenue from current billing cycle", async () => {
      mockPrisma.billing_cycles.findFirst.mockResolvedValue({
        id: "cycle-1",
        status: "ACTIVE",
      });
      mockPrisma.commission_records.aggregate.mockResolvedValue({
        _sum: { attributed_revenue: 1000, commission_earned: 30 },
      });

      const result = await getUsageRevenueData("shop-1");

      expect(result.attributedRevenue).toBe(1000);
      expect(result.commissionEarned).toBe(30);
    });

    it("returns zeros when no active billing cycle", async () => {
      mockPrisma.billing_cycles.findFirst.mockResolvedValue(null);

      const result = await getUsageRevenueData("shop-1");

      expect(result.attributedRevenue).toBe(0);
      expect(result.commissionEarned).toBe(0);
    });
  });

  // ─── getCurrentCycleMetrics ────────────────────────────────────────────

  describe("getCurrentCycleMetrics", () => {
    it("returns metrics for current billing cycle", async () => {
      const futureDate = new Date(Date.now() + 15 * 24 * 60 * 60 * 1000); // 15 days from now
      mockPrisma.billing_cycles.findFirst.mockResolvedValue({
        id: "cycle-1",
        current_cap_amount: 200,
        end_date: futureDate,
      });
      mockPrisma.commission_records.findMany.mockResolvedValue([
        { status: "RECORDED", attributed_revenue: 100 },
        { status: "RECORDED", attributed_revenue: 200 },
        { status: "INVOICED", attributed_revenue: 50 },
      ]);

      const result = await getCurrentCycleMetrics(
        "shop-1",
        defaultSubscription(),
      );

      expect(result.purchases.count).toBe(3);
      expect(result.purchases.total).toBe(350);
      expect(result.net_revenue).toBe(350);
      expect(result.commission).toBeCloseTo(10.5); // 350 * 0.03
      expect(result.final_commission).toBeCloseTo(10.5); // min(10.5, 200) = 10.5
      expect(result.capped_amount).toBe(200);
      expect(result.days_remaining).toBeGreaterThan(0);
    });

    it("returns zero metrics when no active cycle", async () => {
      mockPrisma.billing_cycles.findFirst.mockResolvedValue(null);

      const result = await getCurrentCycleMetrics(
        "shop-1",
        defaultSubscription(),
      );

      expect(result.purchases.count).toBe(0);
      expect(result.net_revenue).toBe(0);
      expect(result.commission).toBe(0);
    });

    it("caps commission at billing cycle cap amount", async () => {
      const futureDate = new Date(Date.now() + 10 * 24 * 60 * 60 * 1000);
      mockPrisma.billing_cycles.findFirst.mockResolvedValue({
        id: "cycle-1",
        current_cap_amount: 5, // Very low cap
        end_date: futureDate,
      });
      mockPrisma.commission_records.findMany.mockResolvedValue([
        { status: "RECORDED", attributed_revenue: 10000 }, // Would be $300 commission
      ]);

      const result = await getCurrentCycleMetrics(
        "shop-1",
        defaultSubscription(),
      );

      expect(result.commission).toBe(300); // 10000 * 0.03
      expect(result.final_commission).toBe(5); // Capped at 5
    });
  });
});
