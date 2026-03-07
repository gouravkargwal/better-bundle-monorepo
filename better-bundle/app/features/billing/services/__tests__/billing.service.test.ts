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
    started_at: new Date("2024-01-01"),
    subscription_plan_id: "plan-1",
    pricing_tier_id: "tier-1",
    shopify_subscription_id: null,
    shopify_status: null,
    trial_threshold_override: null,
    user_chosen_cap_amount: 100,
    created_at: new Date(),
    pricing_tiers: {
      trial_threshold_amount: 75,
      commission_rate: 0.03,
      currency: "USD",
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
            cappedAmount: { amount: 100, currencyCode: "USD" },
            balanceUsed: { amount: 25, currencyCode: "USD" },
            terms: "Usage-based",
          },
        },
      },
    ],
    ...overrides,
  };
}

// Helper to set up the standard trial mock scenario
function setupTrialMocks(
  trialRevenue: number,
  subscriptionOverrides: any = {},
) {
  // getTrialRevenue calls aggregate once
  mockPrisma.commission_records.aggregate.mockResolvedValue({
    _sum: { attributed_revenue: trialRevenue || null },
  });
  mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
    mockSubscription(subscriptionOverrides),
  );
  mockPrisma.shops.findUnique.mockResolvedValue({
    id: "shop-1",
    currency_code: "USD",
  });
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("BillingService", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  // ─── getBillingState: Trial scenarios ──────────────────────────────────

  describe("getBillingState - trial scenarios", () => {
    it("returns trial_active when revenue is below threshold", async () => {
      setupTrialMocks(50);

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
      expect(result.trialData!.isActive).toBe(true);
      expect(result.trialData!.accumulatedRevenue).toBe(50);
      expect(result.trialData!.thresholdAmount).toBe(75);
      expect(result.trialData!.progress).toBe(67); // round(50/75 * 100)
    });

    it("returns trial_active with 0 revenue for new shops", async () => {
      setupTrialMocks(0);

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
      expect(result.trialData!.accumulatedRevenue).toBe(0);
      expect(result.trialData!.progress).toBe(0);
    });

    it("returns trial_completed when revenue >= threshold (no admin)", async () => {
      // Revenue 100 > threshold 75, no Shopify subscription
      setupTrialMocks(100);

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_completed");
      expect(result.trialData!.isActive).toBe(false);
      expect(result.trialData!.progress).toBe(100);
    });

    it("uses trial_threshold_override when set", async () => {
      setupTrialMocks(80, { trial_threshold_override: 150 });

      const result = await BillingService.getBillingState("shop-1");

      // 80 < 150, still in trial
      expect(result.status).toBe("trial_active");
      expect(result.trialData!.thresholdAmount).toBe(150);
    });

    it("defaults to $75 threshold when no subscription exists", async () => {
      mockPrisma.commission_records.aggregate.mockResolvedValue({
        _sum: { attributed_revenue: 50 },
      });
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null);
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        currency_code: "USD",
      });

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
      expect(result.trialData!.thresholdAmount).toBe(75);
    });

    it("caps progress at 100% when revenue far exceeds threshold", async () => {
      setupTrialMocks(500);

      const result = await BillingService.getBillingState("shop-1");

      // 500 >= 75, trial completed. progress capped at 100
      expect(result.status).toBe("trial_completed");
      expect(result.trialData!.progress).toBe(100);
      expect(result.trialData!.isActive).toBe(false);
    });

    it("exact threshold boundary: revenue == threshold is trial_completed", async () => {
      // Code uses strict less-than: trialRevenue < trialThreshold
      // So 75 < 75 = false → trial completed
      setupTrialMocks(75);

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_completed");
    });

    it("uses shop currency from database for trial data", async () => {
      mockPrisma.commission_records.aggregate.mockResolvedValue({
        _sum: { attributed_revenue: 10 },
      });
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription({
          pricing_tiers: {
            trial_threshold_amount: 75,
            commission_rate: 0.03,
            currency: "EUR",
          },
        }),
      );
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        currency_code: "EUR",
      });

      const result = await BillingService.getBillingState("shop-1");

      expect(result.trialData!.currency).toBe("EUR");
    });

    it("returns trial_active with error on DB exception", async () => {
      mockPrisma.commission_records.aggregate.mockRejectedValue(
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
      // Trial revenue exceeds threshold
      mockPrisma.commission_records.aggregate.mockResolvedValueOnce({
        _sum: { attributed_revenue: 100 },
      });
      // Subscription record
      const sub = mockSubscription({
        subscription_type: "PAID",
        status: "ACTIVE",
        shopify_subscription_id: "gid://shopify/AppSubscription/123",
      });
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(sub);
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});

      // Commission breakdown: no active cycle
      mockPrisma.billing_cycles.findFirst.mockResolvedValue(null);
      // Pending commissions aggregate (no cycle = returns early with 0)
      mockPrisma.commission_records.aggregate
        .mockResolvedValueOnce({ _sum: { commission_charged: 0 } })
        .mockResolvedValueOnce({ _sum: { commission_earned: 0 } });

      const admin = mockAdmin([mockShopifySubscription()]);

      const result = await BillingService.getBillingState("shop-1", admin);

      expect(result.status).toBe("subscription_active");
      expect(result.subscriptionData).toBeDefined();
      expect(result.subscriptionData!.status).toBe("ACTIVE");
      expect(result.subscriptionData!.spendingLimit).toBe(100);
    });

    it("returns subscription_active for PENDING Shopify subscriptions", async () => {
      mockPrisma.commission_records.aggregate.mockResolvedValueOnce({
        _sum: { attributed_revenue: 100 },
      });
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription({
          subscription_type: "PAID",
          status: "ACTIVE",
          shopify_subscription_id: "gid://shopify/AppSubscription/123",
        }),
      );
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});
      mockPrisma.billing_cycles.findFirst.mockResolvedValue(null);

      const admin = mockAdmin([
        mockShopifySubscription({ status: "PENDING" }),
      ]);

      const result = await BillingService.getBillingState("shop-1", admin);

      expect(result.status).toBe("subscription_active");
    });

    it("returns subscription_active without admin when DB has Shopify subscription ID", async () => {
      mockPrisma.commission_records.aggregate.mockResolvedValue({
        _sum: { attributed_revenue: 100 },
      });
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription({
          subscription_type: "PAID",
          status: "ACTIVE",
          shopify_subscription_id: "gid://shopify/AppSubscription/123",
          shopify_status: "ACTIVE",
        }),
      );
      mockPrisma.billing_cycles.findFirst.mockResolvedValue(null);

      // No admin passed
      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("subscription_active");
      expect(result.subscriptionData!.status).toBe("ACTIVE");
    });

    it("syncs Shopify subscription status to database", async () => {
      mockPrisma.commission_records.aggregate.mockResolvedValueOnce({
        _sum: { attributed_revenue: 100 },
      });
      const sub = mockSubscription({ subscription_type: "TRIAL", status: "TRIAL" });
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(sub);
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});
      mockPrisma.billing_cycles.findFirst.mockResolvedValue(null);

      const admin = mockAdmin([mockShopifySubscription()]);

      await BillingService.getBillingState("shop-1", admin);

      // Should sync DB with Shopify data
      expect(mockPrisma.shop_subscriptions.update).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({
            subscription_type: "PAID",
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
      expect(result!.cappedAmount).toBe(100);
      expect(result!.currentUsage).toBe(25);
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
      // When activeSubscriptions is empty, only one findFirst call happens (line 395)
      // looking for a DB record with shopify_subscription_id
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
                          cappedAmount: { amount: 200, currencyCode: "USD" },
                          balanceUsed: { amount: 0, currencyCode: "USD" },
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
      expect(result!.cappedAmount).toBe(200);
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

  // ─── Commission breakdown ──────────────────────────────────────────────

  describe("commission breakdown in subscription data", () => {
    it("calculates expected charge from PENDING commissions", async () => {
      // 1st aggregate call: getTrialRevenue
      mockPrisma.commission_records.aggregate.mockResolvedValueOnce({
        _sum: { attributed_revenue: 100 },
      });

      const sub = mockSubscription({
        subscription_type: "PAID",
        status: "ACTIVE",
        shopify_subscription_id: "gid://shopify/AppSubscription/123",
        shopify_status: "ACTIVE",
        user_chosen_cap_amount: 100,
      });
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(sub);
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});

      // Active billing cycle exists
      mockPrisma.billing_cycles.findFirst.mockResolvedValue({
        id: "cycle-1",
        status: "ACTIVE",
      });

      // 2nd aggregate call: pending commissions
      mockPrisma.commission_records.aggregate.mockResolvedValueOnce({
        _sum: { commission_charged: 10 },
      });
      // 3rd aggregate call: rejected commissions
      mockPrisma.commission_records.aggregate.mockResolvedValueOnce({
        _sum: { commission_earned: 2 },
      });

      const admin = mockAdmin([
        mockShopifySubscription({
          lineItems: [
            {
              plan: {
                pricingDetails: {
                  cappedAmount: { amount: 100, currencyCode: "USD" },
                  balanceUsed: { amount: 15, currencyCode: "USD" },
                },
              },
            },
          ],
        }),
      ]);

      const result = await BillingService.getBillingState("shop-1", admin);

      expect(result.subscriptionData!.shopifyUsage).toBe(15);
      expect(result.subscriptionData!.expectedCharge).toBe(10);
      expect(result.subscriptionData!.currentUsage).toBe(25); // 15 + 10
      expect(result.subscriptionData!.rejectedAmount).toBe(2);
    });

    it("returns zero expected charge when no active billing cycle", async () => {
      mockPrisma.commission_records.aggregate.mockResolvedValueOnce({
        _sum: { attributed_revenue: 100 },
      });
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription({
          subscription_type: "PAID",
          status: "ACTIVE",
          shopify_subscription_id: "gid://shopify/AppSubscription/123",
          shopify_status: "ACTIVE",
        }),
      );
      mockPrisma.shop_subscriptions.update.mockResolvedValue({});
      mockPrisma.billing_cycles.findFirst.mockResolvedValue(null);

      const admin = mockAdmin([mockShopifySubscription()]);
      const result = await BillingService.getBillingState("shop-1", admin);

      expect(result.subscriptionData!.expectedCharge).toBe(0);
      expect(result.subscriptionData!.rejectedAmount).toBe(0);
    });
  });
});
