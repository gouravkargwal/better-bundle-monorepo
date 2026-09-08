import { describe, it, expect, vi, beforeEach } from "vitest";

const { mockPrisma } = vi.hoisted(() => ({
  mockPrisma: {
    shops: {
      findUnique: vi.fn(),
    },
  },
}));

vi.mock("../../db.server", () => ({ default: mockPrisma }));
vi.mock("../../utils/logger", () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

import { getShopOnboardingCompleted } from "../shop.service";

function defaultShopRecord() {
  return {
    id: "shop-1",
    shop_domain: "test.myshopify.com",
    access_token: "shpat_test",
    currency_code: "USD",
    email: "test@test.com",
    is_active: true,
    onboarding_completed: true,
    shopify_plus: false,
  };
}

describe("shop.service", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

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
});
