import { describe, it, expect, vi, beforeEach } from "vitest";

// ── Hoisted mocks ──────────────────────────────────────────────────────────

const { mockPrisma } = vi.hoisted(() => ({
  mockPrisma: {
    shop_subscriptions: {
      findFirst: vi.fn(),
      update: vi.fn(),
    },
    shops: { findUnique: vi.fn() },
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
    status: "TRIAL",
    is_active: true,
    started_at: new Date("2024-01-01"),
    subscription_plan_id: "plan-1",
    shopify_subscription_id: null,
    shopify_status: null,
    created_at: new Date(),
    subscription_plans: {
      monthly_price: 99.0,
      trial_days: 14,
    },
    ...overrides,
  };
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
    lineItems: [
      {
        plan: {
          pricingDetails: {
            price: { amount: 99.0, currencyCode: "USD" },
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
    it("returns trial_active when no Shopify subscription exists", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription(),
      );
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        currency_code: "USD",
      });

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
      expect(result.trialData!.isActive).toBe(true);
      expect(result.trialData!.trialDays).toBe(14);
      expect(result.trialData!.monthlyPrice).toBe(99.0);
    });

    it("defaults to $99/14 days when no subscription exists", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null);
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        currency_code: "USD",
      });

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
      expect(result.trialData!.trialDays).toBe(14);
      expect(result.trialData!.monthlyPrice).toBe(99.0);
    });

    it("uses shop currency from database for trial data", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription(),
      );
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        currency_code: "EUR",
      });

      const result = await BillingService.getBillingState("shop-1");

      expect(result.trialData!.currency).toBe("EUR");
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
    it("returns subscription_active when Shopify has active subscription", async () => {
      const sub = mockSubscription({
        status: "ACTIVE",
        shopify_subscription_id: "gid://shopify/AppSubscription/123",
      });
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(sub);
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        currency_code: "USD",
      });

      const admin = mockAdmin([mockShopifySubscription()]);

      const result = await BillingService.getBillingState("shop-1", admin);

      expect(result.status).toBe("subscription_active");
      expect(result.subscriptionData).toBeDefined();
      expect(result.subscriptionData!.status).toBe("ACTIVE");
      expect(result.subscriptionData!.monthlyPrice).toBe(99.0);
    });

    it("returns subscription_pending for PENDING Shopify subscriptions", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription({
          status: "TRIAL",
          shopify_subscription_id: "gid://shopify/AppSubscription/123",
        }),
      );
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        currency_code: "USD",
      });

      const admin = mockAdmin([
        mockShopifySubscription({ status: "PENDING" }),
      ]);

      const result = await BillingService.getBillingState("shop-1", admin);

      expect(result.status).toBe("subscription_pending");
    });

    it("returns subscription_active without admin when DB has Shopify subscription ID", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription({
          status: "ACTIVE",
          shopify_subscription_id: "gid://shopify/AppSubscription/123",
          shopify_status: "ACTIVE",
        }),
      );
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        currency_code: "USD",
      });

      // No admin passed
      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("subscription_active");
      expect(result.subscriptionData!.status).toBe("ACTIVE");
    });

    it("syncs Shopify subscription status to database", async () => {
      const sub = mockSubscription({ status: "TRIAL" });
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(sub);
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        currency_code: "USD",
      });

      const admin = mockAdmin([mockShopifySubscription()]);

      await BillingService.getBillingState("shop-1", admin);

      // Should sync DB with Shopify data
      expect(mockPrisma.shop_subscriptions.update).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({
            status: "ACTIVE",
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
      expect(result!.subscriptionId).toBe(
        "gid://shopify/AppSubscription/123",
      );
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

    it("falls back to node query when DB has subscription ID but not in activeSubscriptions", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue({
        shopify_subscription_id: "gid://shopify/AppSubscription/456",
        shopify_status: "ACTIVE",
      });

      const admin = {
        graphql: vi
          .fn()
          .mockResolvedValueOnce({
            json: vi.fn().mockResolvedValue({
              data: {
                currentAppInstallation: { activeSubscriptions: [] },
              },
            }),
          })
          .mockResolvedValueOnce({
            json: vi.fn().mockResolvedValue({
              data: {
                node: {
                  id: "gid://shopify/AppSubscription/456",
                  status: "PENDING",
                  lineItems: [
                    {
                      plan: {
                        pricingDetails: {
                          price: { amount: 99.0, currencyCode: "USD" },
                          interval: "EVERY_30_DAYS",
                        },
                      },
                    },
                  ],
                },
              },
            }),
          }),
      };

      const result = await BillingService.getShopifySubscriptionStatus(
        "shop-1",
        admin,
      );

      expect(result).not.toBeNull();
      expect(result!.status).toBe("PENDING");
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
