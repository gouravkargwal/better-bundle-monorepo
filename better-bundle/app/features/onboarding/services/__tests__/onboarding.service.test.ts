import { describe, it, expect, vi, beforeEach } from "vitest";

// ── Hoisted mocks (vi.mock factories are hoisted, so variables must be too) ──

const { mockPrisma, mockPublishDataJobEvent } = vi.hoisted(() => {
  const mockPublishDataJobEvent = vi.fn().mockResolvedValue("msg:0:0");
  return {
    mockPrisma: {
      subscription_plans: { findFirst: vi.fn() },
      pricing_tiers: { findFirst: vi.fn() },
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

function mockAdmin(shopData: any = defaultShopData(), graphqlOverrides?: any) {
  return {
    graphql: vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue({
        data: { shop: shopData },
        ...graphqlOverrides,
      }),
    }),
  };
}

function mockAdminWebPixelSuccess(admin: any) {
  // First call = shop query, subsequent calls = web pixel mutation
  const originalGraphql = admin.graphql;
  let callCount = 0;
  admin.graphql = vi.fn().mockImplementation((...args: any[]) => {
    callCount++;
    if (callCount === 1) {
      // Shop info query (for completeOnboarding)
      return originalGraphql(...args);
    }
    // Web pixel mutation
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
  });
  return admin;
}

function mockAdminWebPixelTaken(admin: any) {
  const originalGraphql = admin.graphql;
  let callCount = 0;
  admin.graphql = vi.fn().mockImplementation((...args: any[]) => {
    callCount++;
    if (callCount === 1) {
      return originalGraphql(...args);
    }
    return Promise.resolve({
      json: () =>
        Promise.resolve({
          data: {
            webPixelCreate: {
              userErrors: [
                { code: "TAKEN", field: null, message: "Already exists" },
              ],
              webPixel: null,
            },
          },
        }),
    });
  });
  return admin;
}

function defaultShopData() {
  return {
    id: "gid://shopify/Shop/1",
    name: "Test Store",
    myshopifyDomain: "test-store.myshopify.com",
    primaryDomain: { host: "test-store.com", url: "https://test-store.com" },
    email: "test@test-store.com",
    currencyCode: "USD",
    plan: { displayName: "Basic" },
  };
}

function defaultPlan() {
  return {
    id: "plan-1",
    name: "Default Plan",
    is_active: true,
    is_default: true,
  };
}

function defaultPricingTier() {
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

function defaultSession() {
  return {
    shop: "test-store.myshopify.com",
    accessToken: "shpat_test_token_123",
  };
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
    onboarding_completed: true,
    shopify_plus: false,
  };
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("OnboardingService", () => {
  let service: OnboardingService;

  beforeEach(() => {
    vi.clearAllMocks();
    service = new OnboardingService();
  });

  // ─── getOnboardingData ─────────────────────────────────────────────────

  describe("getOnboardingData", () => {
    it("returns pricing tier config for shop currency", async () => {
      const admin = mockAdmin();
      mockPrisma.subscription_plans.findFirst.mockResolvedValue(defaultPlan());
      mockPrisma.pricing_tiers.findFirst.mockResolvedValue(
        defaultPricingTier(),
      );

      const result = await service.getOnboardingData(
        "test-store.myshopify.com",
        admin,
      );

      expect(result.pricingTier).toEqual({
        symbol: "$",
        threshold_amount: 75,
      });
    });

    it("throws when no default subscription plan exists", async () => {
      const admin = mockAdmin();
      mockPrisma.subscription_plans.findFirst.mockResolvedValue(null);

      await expect(
        service.getOnboardingData("test-store.myshopify.com", admin),
      ).rejects.toThrow("Failed to get onboarding data");
    });

    it("throws when no pricing tier found for currency", async () => {
      const admin = mockAdmin({
        ...defaultShopData(),
        currencyCode: "XYZ",
      });
      mockPrisma.subscription_plans.findFirst.mockResolvedValue(defaultPlan());
      mockPrisma.pricing_tiers.findFirst.mockResolvedValue(null);

      await expect(
        service.getOnboardingData("test-store.myshopify.com", admin),
      ).rejects.toThrow("Failed to get onboarding data");
    });

    it("throws when Shopify API returns no shop data", async () => {
      const admin = {
        graphql: vi.fn().mockResolvedValue({
          json: vi
            .fn()
            .mockResolvedValue({ data: { shop: null }, errors: null }),
        }),
      };

      await expect(
        service.getOnboardingData("test-store.myshopify.com", admin),
      ).rejects.toThrow("Failed to get onboarding data");
    });

    it("throws when Shopify GraphQL call fails", async () => {
      const admin = {
        graphql: vi.fn().mockRejectedValue(new Error("Network error")),
      };

      await expect(
        service.getOnboardingData("test-store.myshopify.com", admin),
      ).rejects.toThrow("Failed to get onboarding data");
    });
  });

  // ─── completeOnboarding ────────────────────────────────────────────────

  describe("completeOnboarding", () => {
    it("runs full onboarding flow: shop creation, trial activation, web pixel, analysis", async () => {
      const admin = mockAdminWebPixelSuccess(mockAdmin());
      const session = defaultSession();

      // Mock $transaction to execute the callback with a mock tx
      const mockTx = {
        shops: {
          findUnique: vi.fn().mockResolvedValue(null), // No existing shop
          upsert: vi.fn().mockResolvedValue(defaultShopRecord()),
          update: vi.fn().mockResolvedValue(defaultShopRecord()),
        },
        shop_subscriptions: {
          findFirst: vi.fn().mockResolvedValue(null), // No existing subscription
          create: vi.fn().mockResolvedValue({
            id: "sub-1",
            shop_id: "shop-uuid-1",
            subscription_type: "TRIAL",
            status: "TRIAL",
            is_active: true,
          }),
        },
        subscription_plans: {
          findFirst: vi.fn().mockResolvedValue(defaultPlan()),
        },
        pricing_tiers: {
          findFirst: vi.fn().mockResolvedValue(defaultPricingTier()),
        },
      };
      mockPrisma.$transaction.mockImplementation(async (cb: any) => cb(mockTx));

      // Mock for triggerAnalysis — shop lookup
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-uuid-1",
        access_token: "shpat_test_token_123",
      });

      await service.completeOnboarding(session, admin);

      // Verify shop was upserted (created)
      expect(mockTx.shops.upsert).toHaveBeenCalledWith(
        expect.objectContaining({
          where: { shop_domain: "test-store.myshopify.com" },
          create: expect.objectContaining({
            shop_domain: "test-store.myshopify.com",
            access_token: "shpat_test_token_123",
            is_active: true,
            onboarding_completed: false,
          }),
        }),
      );

      // Verify trial subscription was created
      expect(mockTx.shop_subscriptions.create).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({
            shop_id: "shop-uuid-1",
            subscription_type: "TRIAL",
            status: "TRIAL",
            is_active: true,
          }),
        }),
      );

      // Verify onboarding was marked completed (outside transaction, after Kafka)
      expect(mockPrisma.shops.update).toHaveBeenCalledWith({
        where: { shop_domain: "test-store.myshopify.com" },
        data: { onboarding_completed: true },
      });

      // Verify Kafka analysis event was published
      expect(mockPublishDataJobEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          event_type: "data_collection",
          shop_id: "shop-uuid-1",
          job_type: "data_collection",
          mode: "historical",
          collection_payload: {
            data_types: ["products", "orders", "customers", "collections"],
          },
          trigger_source: "analysis",
        }),
      );
    });

    it("handles reinstall: preserves onboarding status for reinstalled shops", async () => {
      const admin = mockAdminWebPixelSuccess(mockAdmin());
      const session = defaultSession();

      const existingInactiveShop = {
        ...defaultShopRecord(),
        is_active: false,
        onboarding_completed: true,
      };

      const mockTx = {
        shops: {
          findUnique: vi.fn().mockResolvedValue(existingInactiveShop),
          upsert: vi.fn().mockResolvedValue({
            ...defaultShopRecord(),
            onboarding_completed: true,
          }),
          update: vi.fn().mockResolvedValue(defaultShopRecord()),
        },
        shop_subscriptions: {
          findFirst: vi.fn().mockResolvedValue({
            id: "existing-sub",
            is_active: true,
          }), // Existing subscription
          create: vi.fn(),
        },
        subscription_plans: { findFirst: vi.fn() },
        pricing_tiers: { findFirst: vi.fn() },
      };
      mockPrisma.$transaction.mockImplementation(async (cb: any) => cb(mockTx));
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-uuid-1",
        access_token: "shpat_test_token_123",
      });

      await service.completeOnboarding(session, admin);

      // Verify upsert was called — the update path should NOT reset onboarding
      const upsertCall = mockTx.shops.upsert.mock.calls[0][0];
      // When it's a reinstall with onboarding_completed=true, the update should NOT include onboarding_completed: false
      expect(upsertCall.update).not.toHaveProperty("onboarding_completed");
    });

    it("skips subscription creation when one already exists (idempotency)", async () => {
      const admin = mockAdminWebPixelSuccess(mockAdmin());
      const session = defaultSession();

      const mockTx = {
        shops: {
          findUnique: vi.fn().mockResolvedValue(null),
          upsert: vi.fn().mockResolvedValue(defaultShopRecord()),
          update: vi.fn().mockResolvedValue(defaultShopRecord()),
        },
        shop_subscriptions: {
          findFirst: vi.fn().mockResolvedValue({
            id: "existing-sub",
            is_active: true,
            status: "TRIAL",
          }),
          create: vi.fn(),
        },
        subscription_plans: { findFirst: vi.fn() },
        pricing_tiers: { findFirst: vi.fn() },
      };
      mockPrisma.$transaction.mockImplementation(async (cb: any) => cb(mockTx));
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-uuid-1",
        access_token: "shpat_test_token_123",
      });

      await service.completeOnboarding(session, admin);

      // Should NOT create a new subscription
      expect(mockTx.shop_subscriptions.create).not.toHaveBeenCalled();
    });

    it("handles web pixel TAKEN error gracefully (pixel already exists)", async () => {
      const admin = mockAdminWebPixelTaken(mockAdmin());
      const session = defaultSession();

      const mockTx = {
        shops: {
          findUnique: vi.fn().mockResolvedValue(null),
          upsert: vi.fn().mockResolvedValue(defaultShopRecord()),
          update: vi.fn().mockResolvedValue(defaultShopRecord()),
        },
        shop_subscriptions: {
          findFirst: vi.fn().mockResolvedValue(null),
          create: vi.fn().mockResolvedValue({
            id: "sub-1",
            shop_id: "shop-uuid-1",
            subscription_type: "TRIAL",
            status: "TRIAL",
          }),
        },
        subscription_plans: {
          findFirst: vi.fn().mockResolvedValue(defaultPlan()),
        },
        pricing_tiers: {
          findFirst: vi.fn().mockResolvedValue(defaultPricingTier()),
        },
      };
      mockPrisma.$transaction.mockImplementation(async (cb: any) => cb(mockTx));
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-uuid-1",
        access_token: "shpat_test_token_123",
      });

      // Should NOT throw even though pixel creation returns TAKEN
      await expect(
        service.completeOnboarding(session, admin),
      ).resolves.toBeUndefined();
    });

    it("throws when no default plan exists during trial activation", async () => {
      const admin = mockAdmin();
      const session = defaultSession();

      const mockTx = {
        shops: {
          findUnique: vi.fn().mockResolvedValue(null),
          upsert: vi.fn().mockResolvedValue(defaultShopRecord()),
          update: vi.fn(),
        },
        shop_subscriptions: {
          findFirst: vi.fn().mockResolvedValue(null),
          create: vi.fn(),
        },
        subscription_plans: {
          findFirst: vi.fn().mockResolvedValue(null), // No plan!
        },
        pricing_tiers: { findFirst: vi.fn() },
      };
      mockPrisma.$transaction.mockImplementation(async (cb: any) => cb(mockTx));

      await expect(
        service.completeOnboarding(session, admin),
      ).rejects.toThrow("Failed to complete onboarding");
    });

    it("throws when no pricing tier for shop currency during trial activation", async () => {
      const admin = mockAdmin();
      const session = defaultSession();

      const mockTx = {
        shops: {
          findUnique: vi.fn().mockResolvedValue(null),
          upsert: vi.fn().mockResolvedValue({
            ...defaultShopRecord(),
            currency_code: "EUR",
          }),
          update: vi.fn(),
        },
        shop_subscriptions: {
          findFirst: vi.fn().mockResolvedValue(null),
          create: vi.fn(),
        },
        subscription_plans: {
          findFirst: vi.fn().mockResolvedValue(defaultPlan()),
        },
        pricing_tiers: {
          findFirst: vi.fn().mockResolvedValue(null), // No tier for EUR!
        },
      };
      mockPrisma.$transaction.mockImplementation(async (cb: any) => cb(mockTx));

      await expect(
        service.completeOnboarding(session, admin),
      ).rejects.toThrow("Failed to complete onboarding");
    });

    it("detects Shopify Plus shops from plan name", async () => {
      const plusShopData = {
        ...defaultShopData(),
        plan: { displayName: "Shopify Plus", shopifyPlus: true },
      };
      const admin = mockAdminWebPixelSuccess(mockAdmin(plusShopData));
      const session = defaultSession();

      const mockTx = {
        shops: {
          findUnique: vi.fn().mockResolvedValue(null),
          upsert: vi.fn().mockResolvedValue({
            ...defaultShopRecord(),
            shopify_plus: true,
          }),
          update: vi.fn().mockResolvedValue(defaultShopRecord()),
        },
        shop_subscriptions: {
          findFirst: vi.fn().mockResolvedValue(null),
          create: vi.fn().mockResolvedValue({
            id: "sub-1",
            shop_id: "shop-uuid-1",
            subscription_type: "TRIAL",
            status: "TRIAL",
          }),
        },
        subscription_plans: {
          findFirst: vi.fn().mockResolvedValue(defaultPlan()),
        },
        pricing_tiers: {
          findFirst: vi.fn().mockResolvedValue(defaultPricingTier()),
        },
      };
      mockPrisma.$transaction.mockImplementation(async (cb: any) => cb(mockTx));
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-uuid-1",
        access_token: "shpat_test_token_123",
      });

      await service.completeOnboarding(session, admin);

      // Verify shopify_plus was set in create/update
      const upsertCall = mockTx.shops.upsert.mock.calls[0][0];
      expect(upsertCall.create.shopify_plus).toBe(true);
      expect(upsertCall.update.shopify_plus).toBe(true);
    });

    it("web pixel failure does not break onboarding flow", async () => {
      // Admin that fails on web pixel mutation
      const admin = mockAdmin();
      let callCount = 0;
      admin.graphql = vi.fn().mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          // Shop info query
          return Promise.resolve({
            json: () =>
              Promise.resolve({ data: { shop: defaultShopData() } }),
          });
        }
        // Web pixel mutation throws
        return Promise.reject(new Error("Web pixel API down"));
      });

      const session = defaultSession();

      const mockTx = {
        shops: {
          findUnique: vi.fn().mockResolvedValue(null),
          upsert: vi.fn().mockResolvedValue(defaultShopRecord()),
          update: vi.fn().mockResolvedValue(defaultShopRecord()),
        },
        shop_subscriptions: {
          findFirst: vi.fn().mockResolvedValue(null),
          create: vi.fn().mockResolvedValue({
            id: "sub-1",
            shop_id: "shop-uuid-1",
            subscription_type: "TRIAL",
            status: "TRIAL",
          }),
        },
        subscription_plans: {
          findFirst: vi.fn().mockResolvedValue(defaultPlan()),
        },
        pricing_tiers: {
          findFirst: vi.fn().mockResolvedValue(defaultPricingTier()),
        },
      };
      mockPrisma.$transaction.mockImplementation(async (cb: any) => cb(mockTx));
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-uuid-1",
        access_token: "shpat_test_token_123",
      });

      // Web pixel failure should NOT prevent the rest of onboarding
      // The service catches web pixel errors internally
      // But triggerAnalysis should still run
      await expect(
        service.completeOnboarding(session, admin),
      ).resolves.toBeUndefined();

      // Kafka event should still be sent
      expect(mockPublishDataJobEvent).toHaveBeenCalled();
    });

    it("publishes correct Kafka data collection event on success", async () => {
      const admin = mockAdminWebPixelSuccess(mockAdmin());
      const session = defaultSession();

      const mockTx = {
        shops: {
          findUnique: vi.fn().mockResolvedValue(null),
          upsert: vi.fn().mockResolvedValue(defaultShopRecord()),
          update: vi.fn().mockResolvedValue(defaultShopRecord()),
        },
        shop_subscriptions: {
          findFirst: vi.fn().mockResolvedValue(null),
          create: vi.fn().mockResolvedValue({
            id: "sub-1",
            shop_id: "shop-uuid-1",
            subscription_type: "TRIAL",
            status: "TRIAL",
          }),
        },
        subscription_plans: {
          findFirst: vi.fn().mockResolvedValue(defaultPlan()),
        },
        pricing_tiers: {
          findFirst: vi.fn().mockResolvedValue(defaultPricingTier()),
        },
      };
      mockPrisma.$transaction.mockImplementation(async (cb: any) => cb(mockTx));
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-uuid-1",
        access_token: "shpat_test_token_123",
      });

      await service.completeOnboarding(session, admin);

      const kafkaPayload = mockPublishDataJobEvent.mock.calls[0][0];
      expect(kafkaPayload).toMatchObject({
        event_type: "data_collection",
        shop_id: "shop-uuid-1",
        job_type: "data_collection",
        mode: "historical",
        trigger_source: "analysis",
        collection_payload: {
          data_types: ["products", "orders", "customers", "collections"],
        },
      });
      expect(kafkaPayload.job_id).toMatch(/^analysis_test-store\.myshopify\.com_/);
      expect(kafkaPayload.timestamp).toBeDefined();
    });
  });
});
