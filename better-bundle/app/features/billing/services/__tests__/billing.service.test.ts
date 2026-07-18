import { describe, it, expect, vi, beforeEach } from "vitest";

// ── Hoisted mocks ──────────────────────────────────────────────────────────

const { mockPrisma } = vi.hoisted(() => ({
  mockPrisma: {
    commission_records: { aggregate: vi.fn() },
    shop_subscriptions: {
      findFirst: vi.fn(),
      update: vi.fn(),
    },
    shops: { findUnique: vi.fn() },
    billing_cycles: { findFirst: vi.fn() },
  },
}));

vi.mock("../../../../db.server", () => ({ default: mockPrisma }));
vi.mock("app/utils/logger", () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

import { BillingService } from "../billing.service";

// ── Helpers ────────────────────────────────────────────────────────────────

function mockSubscription(overrides: any = {}) {
  return {
    id: "sub-1",
    shop_id: "shop-1",
    subscription_type: "TRIAL",
    status: "TRIAL",
    is_active: true,
    started_at: new Date(), // now so trial is active
    subscription_plan_id: "plan-1",
    shopify_subscription_id: null,
    shopify_status: null,
    monthly_fee_override: null,
    trial_duration_days: null,
    created_at: new Date(),
    subscription_plans: {
      name: "Pro",
      monthly_fee: 29,
      trial_days: 14,
    },
    ...overrides,
  };
}

function mockExpiredSubscription(overrides: any = {}) {
  // started_at in the past so trial is expired
  const pastDate = new Date();
  pastDate.setDate(pastDate.getDate() - 20); // 20 days ago, with 14-day trial

  return mockSubscription({
    started_at: pastDate,
    ...overrides,
  });
}

function mockPaidSubscription(overrides: any = {}) {
  return mockSubscription({
    subscription_type: "PAID",
    status: "ACTIVE",
    shopify_subscription_id: "gid://shopify/AppSubscription/123",
    ...overrides,
  });
}

function mockAdmin(activeSubscriptions: any[] = []) {
  return {
    graphql: vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue({
        data: {
          currentAppInstallation: {
            activeSubscriptions,
          },
        },
      }),
    }),
  };
}

function mockShopifySubscription(overrides: any = {}) {
  return {
    id: "gid://shopify/AppSubscription/123",
    name: "BetterBundle",
    status: "ACTIVE",
    test: false,
    currentPeriodEnd: "2024-02-01T00:00:00Z",
    lineItems: [
      {
        plan: {
          pricingDetails: {
            __typename: "AppRecurringPricing",
            price: { amount: 29, currencyCode: "USD" },
            interval: "EVERY_30_DAYS",
          },
        },
      },
    ],
    ...overrides,
  };
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("BillingService", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  // ─── getBillingState: Trial scenarios ──────────────────────────────────

  describe("getBillingState - trial scenarios", () => {
    it("returns trial_active when trial is still in progress", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription(),
      );

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
      expect(result.trialData!.isActive).toBe(true);
      // Should have positive daysRemaining since started_at is now
      expect(result.trialData!.daysRemaining).toBeGreaterThan(0);
      expect(result.trialData!.trialDays).toBe(14);
    });

    it("returns trial_active with no subscription (new shop)", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null);
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        currency_code: "USD",
      });

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
      expect(result.trialData!.isActive).toBe(true);
      expect(result.trialData!.trialDays).toBe(14);
      expect(result.trialData!.currency).toBe("USD");
    });

    it("returns trial_completed when trial period has expired", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockExpiredSubscription(),
      );

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_completed");
      expect(result.trialData!.isActive).toBe(false);
      expect(result.trialData!.daysRemaining).toBe(0);
    });

    it("uses trial_duration_days from subscription when set", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription({
          trial_duration_days: 30,
        }),
      );

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
      expect(result.trialData!.trialDays).toBe(30);
    });

    it("uses USD as default currency for trial data", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription(),
      );

      const result = await BillingService.getBillingState("shop-1");

      expect(result.trialData!.currency).toBe("USD");
    });

    it("returns trial_active with error on DB exception", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockRejectedValue(
        new Error("DB down"),
      );

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
      expect(result.error).toBeDefined();
      expect(result.error!.code).toBe("BILLING_ERROR");
    });
  });

  // ─── getBillingState: Subscription scenarios ───────────────────────────

  describe("getBillingState - subscription scenarios", () => {
    it("returns subscription_active when Shopify has active recurring subscription", async () => {
      const sub = mockPaidSubscription();
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(sub);
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});

      const admin = mockAdmin([mockShopifySubscription()]);

      const result = await BillingService.getBillingState("shop-1", admin);

      expect(result.status).toBe("subscription_active");
      expect(result.subscriptionData).toBeDefined();
      expect(result.subscriptionData!.status).toBe("ACTIVE");
      expect(result.subscriptionData!.monthlyFee).toBe(29);
      expect(result.subscriptionData!.planName).toBe("Pro");
    });

    it("returns subscription_active for PENDING Shopify subscriptions", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockPaidSubscription(),
      );
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});

      const admin = mockAdmin([mockShopifySubscription({ status: "PENDING" })]);

      const result = await BillingService.getBillingState("shop-1", admin);

      expect(result.status).toBe("subscription_active");
    });

    it("returns subscription_active without admin when DB has Shopify subscription ID", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockPaidSubscription({
          shopify_status: "ACTIVE",
        }),
      );

      // No admin passed
      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("subscription_active");
      expect(result.subscriptionData!.status).toBe("ACTIVE");
      expect(result.subscriptionData!.monthlyFee).toBe(29);
    });

    it("syncs Shopify subscription status to database", async () => {
      // Use PAID subscription so the flow reaches the isPaidPhase block
      // where getShopifySubscriptionStatus is called and syncs the DB
      const sub = mockPaidSubscription();
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(sub);
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});

      const admin = mockAdmin([mockShopifySubscription()]);

      await BillingService.getBillingState("shop-1", admin);

      // Should sync DB with Shopify data (update is called inside getShopifySubscriptionStatus)
      expect(mockPrisma.shop_subscriptions.update).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({
            subscription_type: "PAID",
            shopify_subscription_id: "gid://shopify/AppSubscription/123",
          }),
        }),
      );
    });
  });

  // ─── getShopifySubscriptionStatus ──────────────────────────────────────

  describe("getShopifySubscriptionStatus", () => {
    it("returns subscription details from Shopify GraphQL", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription(),
      );
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});

      const admin = mockAdmin([mockShopifySubscription()]);
      const result = await BillingService.getShopifySubscriptionStatus(
        "shop-1",
        admin,
      );

      expect(result).not.toBeNull();
      expect(result!.status).toBe("ACTIVE");
      expect(result!.subscriptionId).toBe("gid://shopify/AppSubscription/123");
      expect(result!.monthlyFee).toBe(29);
      expect(result!.currency).toBe("USD");
    });

    it("returns null when no active subscriptions and no DB record", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null);

      const admin = mockAdmin([]);
      const result = await BillingService.getShopifySubscriptionStatus(
        "shop-1",
        admin,
      );

      expect(result).toBeNull();
    });

    it("returns null when no active Shopify subscriptions", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue({
        shopify_subscription_id: "gid://shopify/AppSubscription/456",
        shopify_status: "ACTIVE",
      });

      const admin = {
        graphql: vi.fn().mockResolvedValueOnce({
          json: vi.fn().mockResolvedValue({
            data: {
              currentAppInstallation: { activeSubscriptions: [] },
            },
          }),
        }),
      };

      const result = await BillingService.getShopifySubscriptionStatus(
        "shop-1",
        admin,
      );

      expect(result).toBeNull();
    });

    it("returns null when GraphQL fails", async () => {
      const admin = {
        graphql: vi.fn().mockRejectedValue(new Error("GraphQL failed")),
      };

      const result = await BillingService.getShopifySubscriptionStatus(
        "shop-1",
        admin,
      );

      expect(result).toBeNull();
    });

    it("handles DB sync failure gracefully", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription(),
      );
      mockPrisma.shop_subscriptions.update.mockRejectedValue(
        new Error("DB write failed"),
      );

      const admin = mockAdmin([mockShopifySubscription()]);
      const result = await BillingService.getShopifySubscriptionStatus(
        "shop-1",
        admin,
      );

      // Returns data even if DB sync fails
      expect(result).not.toBeNull();
      expect(result!.status).toBe("ACTIVE");
    });
  });
});
