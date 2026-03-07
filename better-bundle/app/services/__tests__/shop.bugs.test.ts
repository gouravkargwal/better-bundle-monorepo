/**
 * BUG-CATCHING TESTS for shop.service.ts
 *
 * These tests expose real bugs in the code.
 * They should FAIL before fixes and PASS after fixes.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

const { mockPrisma } = vi.hoisted(() => ({
  mockPrisma: {
    shops: {
      findUnique: vi.fn(),
      upsert: vi.fn(),
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
  getShopSubscription,
  deactivateShopBilling,
} from "../shop.service";

// ── Bug-catching tests ─────────────────────────────────────────────────────

describe("shop.service — BUG TESTS", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  // ─── BUG 2: getShopSubscription queries non-existent shop_domain field ─

  describe("BUG 2: getShopSubscription should query by shop_id, not shop_domain", () => {
    it("should query shop_subscriptions using shop_id (via join or lookup), not shop_domain", async () => {
      mockPrisma.shops.findUnique.mockResolvedValue({
        id: "shop-1",
      });
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue({
        id: "sub-1",
        status: "ACTIVE",
      });

      await getShopSubscription("test.myshopify.com");

      // BUG: Current code queries { shop_domain: shopDomain, status: "ACTIVE" }
      // but shop_subscriptions table has NO shop_domain column.
      // It only has shop_id. This will throw a Prisma error at runtime.
      //
      // FIXED: Should first look up the shop by domain to get shop_id,
      // then query shop_subscriptions by shop_id.
      // OR: Use a relation filter like { shops: { shop_domain: shopDomain } }
      const findFirstCall = mockPrisma.shop_subscriptions.findFirst.mock.calls[0][0];
      expect(findFirstCall.where).not.toHaveProperty("shop_domain");
      expect(findFirstCall.where).toHaveProperty("status", "ACTIVE");
    });
  });

  // ─── BUG 3: deactivateShopBilling uses non-existent effective_to field ──

  describe("BUG 3: deactivateShopBilling should use cancelled_at, not effective_to", () => {
    it("should use cancelled_at field instead of non-existent effective_to", async () => {
      mockPrisma.shops.update.mockResolvedValue({ id: "shop-1" });
      mockPrisma.shop_subscriptions.updateMany.mockResolvedValue({ count: 1 });
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null);

      await deactivateShopBilling("test.myshopify.com");

      // BUG: Current code sets { effective_to: new Date() }
      // but shop_subscriptions table has NO effective_to column.
      // It has cancelled_at (DateTime?) instead.
      //
      // FIXED: Should use cancelled_at instead of effective_to
      const updateManyCall = mockPrisma.shop_subscriptions.updateMany.mock.calls[0][0];
      expect(updateManyCall.data).not.toHaveProperty("effective_to");
      expect(updateManyCall.data).toHaveProperty("cancelled_at");
    });
  });

  // ─── BUG 7: deactivateShopBilling step 3 is dead code ──────────────────

  describe("BUG 7: deactivateShopBilling step 3 should not be a useless findFirst", () => {
    it("should not have a dangling findFirst that does nothing", async () => {
      mockPrisma.shops.update.mockResolvedValue({ id: "shop-1" });
      mockPrisma.shop_subscriptions.updateMany.mockResolvedValue({ count: 1 });
      mockPrisma.shop_subscriptions.findFirst.mockResolvedValue(null);

      await deactivateShopBilling("test.myshopify.com");

      // BUG: Current code does findFirst after updateMany but doesn't use the result.
      // The comment says "Create billing event" but nothing is created.
      //
      // FIXED: Remove the dead findFirst call entirely.
      // After fix, findFirst should NOT be called at all in deactivateShopBilling.
      expect(mockPrisma.shop_subscriptions.findFirst).not.toHaveBeenCalled();
    });
  });
});
