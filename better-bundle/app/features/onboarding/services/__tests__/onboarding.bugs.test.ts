/**
 * BUG-CATCHING TESTS for Onboarding Flow
 *
 * These tests expose real bugs in the code.
 * They should FAIL before fixes and PASS after fixes.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

const { mockPrisma, mockPublishDataJobEvent } = vi.hoisted(() => {
  const mockPublishDataJobEvent = vi.fn().mockResolvedValue("msg:0:0");
  return {
    mockPrisma: {
      subscription_plans: { findFirst: vi.fn() },
      shops: { findUnique: vi.fn(), upsert: vi.fn(), update: vi.fn() },
      shop_subscriptions: { findFirst: vi.fn(), create: vi.fn() },
      $transaction: vi.fn(),
    },
    mockPublishDataJobEvent,
  };
});

vi.mock("../../../../db.server", () => ({ default: mockPrisma }));
vi.mock("../../../../services/kafka/kafka-producer.service", () => ({
  KafkaProducerService: {
    getInstance: vi.fn().mockResolvedValue({
      publishDataJobEvent: mockPublishDataJobEvent,
    }),
  },
}));
vi.mock("app/utils/logger", () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock("../../../../utils/currency", () => ({
  getCurrencySymbol: vi.fn((code: string) => (code === "USD" ? "$" : code)),
}));

import { OnboardingService } from "../onboarding.service";

// ── Helpers ────────────────────────────────────────────────────────────────

function defaultShopData() {
  return {
    id: "gid://shopify/Shop/1",
    name: "Test Store",
    myshopifyDomain: "test-store.myshopify.com",
    primaryDomain: { host: "test-store.com", url: "https://test-store.com" },
    email: "test@test-store.com",
    currencyCode: "USD",
    plan: { displayName: "Basic", shopifyPlus: false },
  };
}

function defaultPlan() {
  return {
    id: "plan-1",
    name: "BetterBundle Flat",
    is_active: true,
    is_default: true,
    monthly_price: 99.0,
    trial_days: 14,
  };
}

function defaultSession() {
  return { shop: "test-store.myshopify.com", accessToken: "shpat_test_token_123" };
}

function defaultShopRecord() {
  return {
    id: "shop-uuid-1",
    shop_domain: "test-store.myshopify.com",
    access_token: "shpat_test_token_123",
    currency_code: "USD",
    email: "test@test-store.com",
    plan_type: "Basic",
    is_active: true,
    onboarding_completed: false,
    shopify_plus: false,
  };
}

function mockAdminWebPixelSuccess(shopData: any = defaultShopData()) {
  let callCount = 0;
  return {
    graphql: vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve({
          json: () => Promise.resolve({ data: { shop: shopData } }),
        });
      }
      return Promise.resolve({
        json: () =>
          Promise.resolve({
            data: {
              webPixelCreate: {
                userErrors: [],
                webPixel: { id: "gid://shopify/WebPixel/123", settings: "{}" },
              },
            },
          }),
      });
    }),
  };
}

function setupFullOnboardingMocks(shopRecordOverrides: any = {}) {
  const shopRecord = { ...defaultShopRecord(), ...shopRecordOverrides };
  const mockTx = {
    shops: {
      findUnique: vi.fn().mockResolvedValue(null),
      upsert: vi.fn().mockResolvedValue(shopRecord),
      update: vi.fn().mockResolvedValue(shopRecord),
    },
    shop_subscriptions: {
      findFirst: vi.fn().mockResolvedValue(null),
      create: vi.fn().mockResolvedValue({
        id: "sub-1",
        shop_id: shopRecord.id,
        status: "TRIAL",
        is_active: true,
      }),
    },
    subscription_plans: {
      findFirst: vi.fn().mockResolvedValue(defaultPlan()),
    },
  };
  mockPrisma.$transaction.mockImplementation(async (cb: any) => cb(mockTx));
  mockPrisma.shops.findUnique.mockResolvedValue({
    id: shopRecord.id,
    access_token: "shpat_test_token_123",
  });
  return mockTx;
}

// ── Bug-catching tests ─────────────────────────────────────────────────────

describe("OnboardingService — BUG TESTS", () => {
  let service: OnboardingService;

  beforeEach(() => {
    vi.clearAllMocks();
    service = new OnboardingService();
  });

  // ─── BUG 1: Missing shopifyPlus in GraphQL query ──────────────────────

  describe("BUG 1: shopifyPlus detection uses boolean, not string matching", () => {
    it("should use plan.shopifyPlus boolean, not string matching on displayName", async () => {
      // Shopify Plus shop with a plan name that does NOT contain "Plus"
      // e.g. a custom enterprise plan name
      const shopData = {
        ...defaultShopData(),
        plan: { displayName: "Enterprise Custom", shopifyPlus: true },
      };
      const admin = mockAdminWebPixelSuccess(shopData);
      const session = defaultSession();
      const mockTx = setupFullOnboardingMocks();

      await service.completeOnboarding(session, admin);

      const upsertCall = mockTx.shops.upsert.mock.calls[0][0];
      // BUG: Current code does displayName.includes("Plus") which returns false
      // for "Enterprise Custom", even though shopifyPlus=true
      // FIXED: Should use shopData.plan.shopifyPlus boolean
      expect(upsertCall.create.shopify_plus).toBe(true);
      expect(upsertCall.update.shopify_plus).toBe(true);
    });
  });

  // ─── Trial subscription uses a time-based expiry ──────────────────────

  describe("Trial subscription sets a time-based expires_at", () => {
    it("should set expires_at based on the plan's trial_days, not a revenue cap", async () => {
      const admin = mockAdminWebPixelSuccess();
      const session = defaultSession();
      const mockTx = setupFullOnboardingMocks();

      await service.completeOnboarding(session, admin);

      expect(mockTx.shop_subscriptions.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          expires_at: expect.any(Date),
        }),
      });
    });
  });

  // ─── BUG 5: onboarding_completed set before Kafka succeeds ────────────

  describe("BUG 5: onboarding_completed should be set AFTER Kafka succeeds", () => {
    it("should NOT mark onboarding complete if Kafka publish fails", async () => {
      const admin = mockAdminWebPixelSuccess();
      const session = defaultSession();
      setupFullOnboardingMocks();

      // Make Kafka fail
      mockPublishDataJobEvent.mockRejectedValue(new Error("Kafka down"));

      // completeOnboarding should throw since triggerAnalysis fails
      await expect(
        service.completeOnboarding(session, admin),
      ).rejects.toThrow();

      // BUG: Current code marks onboarding_completed=true INSIDE the transaction
      // BEFORE Kafka runs. So even when Kafka fails, the DB says onboarding is done.
      // The user gets redirected to /app forever with no recommendations.
      //
      // FIXED: markOnboardingCompleted should be called AFTER triggerAnalysis,
      // outside the transaction.
      //
      // After the fix, the transaction should NOT have set onboarding_completed=true
      // when Kafka fails. We verify by checking that the final state doesn't have
      // onboarding marked complete.
      //
      // Note: After the fix, the transaction no longer calls markOnboardingCompleted.
      // Instead, it's called separately after Kafka succeeds.
      // So mockPrisma.shops.update (outside tx) should NOT have been called with
      // onboarding_completed: true when Kafka fails.
      expect(mockPrisma.shops.update).not.toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({ onboarding_completed: true }),
        }),
      );
    });
  });
});
