import { describe, it, expect, vi, beforeEach } from "vitest";
import { MIN_TRIAL_ORDERS } from "../../trialGate";

// ── Hoisted mocks ──────────────────────────────────────────────────────────

const { mockPrisma } = vi.hoisted(() => ({
  mockPrisma: {
    commission_records: { aggregate: vi.fn(), count: vi.fn() },
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
    commission_rate_override: null,
    cap_amount_override: null,
    trial_threshold_override: null,
    created_at: new Date(),
    subscription_plans: {
      name: "Pay As You Go",
      commission_rate: 0.03,
      cap_amount: 299,
      trial_revenue_threshold: 1000,
    },
    ...overrides,
  };
}

// The trial ends on revenue AND orders, so "used up" means both were reached.
// Callers must also stub commission_records to return >= both thresholds.
function mockUsedUpSubscription(overrides: any = {}) {
  return mockSubscription(overrides);
}

/**
 * What the trial has accumulated so far.
 *
 * Orders default past the threshold so revenue-focused tests keep testing
 * revenue. The order condition has its own tests below — see
 * "one large order is money, not evidence".
 */
function stubTrialProgress(amount: number, orders: number = MIN_TRIAL_ORDERS) {
  mockPrisma.commission_records.aggregate.mockResolvedValue({
    _sum: { attributed_revenue: amount },
  });
  mockPrisma.commission_records.count.mockResolvedValue(orders);
}

/** Back-compat alias for the revenue-only tests. */
const stubTrialRevenue = stubTrialProgress;

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
            __typename: "AppUsagePricing",
            terms: "3% of attributed revenue, up to 299 USD per 30 days",
            cappedAmount: { amount: 299, currencyCode: "USD" },
            balanceUsed: { amount: 42, currencyCode: "USD" },
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
      stubTrialRevenue(120);
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription(),
      );

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
      expect(result.trialData!.isActive).toBe(true);
      expect(result.trialData!.trialThreshold).toBe(1000);
      expect(result.trialData!.revenueEarned).toBeLessThan(1000);
    });

    it("returns trial_active with no subscription (new shop)", async () => {
      stubTrialRevenue(0);
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null);
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
        currency_code: "USD",
      });

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
      expect(result.trialData!.isActive).toBe(true);
      expect(result.trialData!.trialThreshold).toBe(1000);
      expect(result.trialData!.currency).toBe("USD");
    });

    it("returns trial_completed once attributed revenue reaches the threshold", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockUsedUpSubscription(),
      );
      stubTrialRevenue(1000);

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_completed");
      expect(result.trialData!.isActive).toBe(false);
    });

    it("one large order is money, not evidence, so the trial continues", async () => {
      // The real case from the stage store: a single attributed order worth
      // $1,110 clears a $1,000 threshold. Ending the trial there asks the
      // merchant to start paying on the strength of one sale, while the Proof
      // page still reads "Not enough data yet".
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockUsedUpSubscription(),
      );
      stubTrialProgress(1110.2, 1);

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
      expect(result.trialData!.ordersEarned).toBe(1);
    });

    it("many small orders are evidence, not money, so the trial continues", async () => {
      // The mirror failure: plenty for the merchant to look at, but we have
      // barely made them anything.
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockUsedUpSubscription(),
      );
      stubTrialProgress(300, MIN_TRIAL_ORDERS);

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
    });

    it("completes only when both conditions are met", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockUsedUpSubscription(),
      );
      stubTrialProgress(1000, MIN_TRIAL_ORDERS);

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_completed");
    });

    it("stays in trial no matter how old the install is", async () => {
      // A year-old install that has generated nothing is still on trial:
      // there is deliberately no elapsed-time gate.
      const old = new Date();
      old.setDate(old.getDate() - 365);
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription({ started_at: old }),
      );
      stubTrialRevenue(10);

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
      expect(result.trialData!.isActive).toBe(true);
    });

    it("uses trial_threshold_override when set", async () => {
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(
        mockSubscription({ trial_threshold_override: 2500 }),
      );
      stubTrialRevenue(0);

      const result = await BillingService.getBillingState("shop-1");

      expect(result.status).toBe("trial_active");
      expect(result.trialData!.trialThreshold).toBe(2500);
    });

    it("uses USD as default currency for trial data", async () => {
      stubTrialRevenue(0);
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
      expect(result.subscriptionData!.commissionRate).toBe(0.03);
      expect(result.subscriptionData!.cappedAmount).toBe(299);
      expect(result.subscriptionData!.usageThisCycle).toBe(42);
      expect(result.subscriptionData!.planName).toBe("Pay As You Go");
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
      expect(result.subscriptionData!.commissionRate).toBe(0.03);
      expect(result.subscriptionData!.cappedAmount).toBe(299);
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
      expect(result!.cappedAmount).toBe(299);
      expect(result!.balanceUsed).toBe(42);
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
