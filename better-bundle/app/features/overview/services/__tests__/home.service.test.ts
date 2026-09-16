import { describe, it, expect, vi, beforeEach } from "vitest";

const { mockPrisma } = vi.hoisted(() => ({
  mockPrisma: {
    $queryRaw: vi.fn(),
    product_data: { findMany: vi.fn() },
  },
}));

vi.mock("../../../../db.server", () => ({ default: mockPrisma }));
vi.mock("../../../impact/services/lift.service", () => ({
  getLiftSummary: vi.fn(),
}));
vi.mock("../../../settings/services/settings.service", () => ({
  getShopSettings: vi.fn(),
}));
vi.mock("../cycle.service", () => ({
  getCycleMetrics: vi.fn(),
}));

import { getSyncStatus, getHomeData } from "../home.service";
import { getShopSettings } from "../../../settings/services/settings.service";
import { getLiftSummary } from "../../../impact/services/lift.service";
import { getCycleMetrics } from "../cycle.service";

describe("home.service - getSyncStatus", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("extracts and formats sync counts and timestamp on happy path", async () => {
    const mockDate = new Date("2026-09-13T10:00:00.000Z");
    mockPrisma.$queryRaw.mockResolvedValueOnce([
      {
        products_total: 142,
        products_active: 138,
        products_embedded: 138,
        products_in_store: 142,
        collections_total: 16,
        orders_total: 1420,
        edges_total: 450,
        edges_observed: 120,
        last_synced_at: mockDate,
      },
    ]);

    const result = await getSyncStatus("shop-123");

    expect(result).toEqual({
      productsTotal: 142,
      productsActive: 138,
      productsEmbedded: 138,
      productsInStore: 142,
      collectionsTotal: 16,
      ordersTotal: 1420,
      edgesTotal: 450,
      edgesObserved: 120,
      lastSyncedAt: "2026-09-13T10:00:00.000Z",
    });
  });

  it("handles null or missing counts gracefully for a new store", async () => {
    mockPrisma.$queryRaw.mockResolvedValueOnce([
      {
        products_total: null,
        products_active: null,
        products_embedded: null,
        collections_total: null,
        orders_total: null,
        edges_total: null,
        edges_observed: null,
        last_synced_at: null,
      },
    ]);

    const result = await getSyncStatus("shop-empty");

    expect(result).toEqual({
      productsTotal: 0,
      productsActive: 0,
      productsEmbedded: 0,
      productsInStore: null,
      collectionsTotal: 0,
      ordersTotal: 0,
      edgesTotal: 0,
      edgesObserved: 0,
      lastSyncedAt: null,
    });
  });

  it("handles empty query results without crashing", async () => {
    mockPrisma.$queryRaw.mockResolvedValueOnce([]);

    const result = await getSyncStatus("shop-no-rows");

    expect(result).toEqual({
      productsTotal: 0,
      productsActive: 0,
      productsEmbedded: 0,
      productsInStore: null,
      collectionsTotal: 0,
      ordersTotal: 0,
      edgesTotal: 0,
      edgesObserved: 0,
      lastSyncedAt: null,
    });
  });

  it("handles database exceptions by returning fallback zero state", async () => {
    mockPrisma.$queryRaw.mockRejectedValueOnce(new Error("DB connection lost"));

    const result = await getSyncStatus("shop-err");

    expect(result).toEqual({
      productsTotal: 0,
      productsActive: 0,
      productsEmbedded: 0,
      productsInStore: null,
      collectionsTotal: 0,
      ordersTotal: 0,
      edgesTotal: 0,
      edgesObserved: 0,
      lastSyncedAt: null,
    });
  });

  it("converts string timestamps to ISO format", async () => {
    mockPrisma.$queryRaw.mockResolvedValueOnce([
      {
        products_total: 10,
        products_active: 8,
        products_embedded: 5,
        collections_total: 2,
        orders_total: 50,
        edges_total: 20,
        edges_observed: 5,
        last_synced_at: "2026-09-13 10:30:00+00",
      },
    ]);

    const result = await getSyncStatus("shop-str-date");

    expect(result.lastSyncedAt).toBe(new Date("2026-09-13 10:30:00+00").toISOString());
  });
});

describe("home.service - getHomeData", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("includes sync status in aggregated HomeData", async () => {
    vi.mocked(getShopSettings).mockResolvedValueOnce({
      shopId: "shop-123",
      shopCurrency: "USD",
      holdoutDisabled: false,
      surfaces: {
        mercury: true,
        apollo: true,
        thank_you: true,
        phoenix: true,
        venus: true,
      },
      detectedSurfaces: {},
    } as any);

    // Mock for getSyncStatus queryRaw
    mockPrisma.$queryRaw.mockResolvedValueOnce([
      {
        products_total: 50,
        products_active: 45,
        products_embedded: 45,
        collections_total: 5,
        orders_total: 100,
        edges_total: 30,
        edges_observed: 10,
        last_synced_at: null,
      },
    ]);

    // Mock for getSurfaceStats queryRaw
    mockPrisma.$queryRaw.mockResolvedValueOnce([]);

    // Mock for getTopProducts queryRaw
    mockPrisma.$queryRaw.mockResolvedValueOnce([]);

    vi.mocked(getLiftSummary).mockResolvedValueOnce({
      state: "insufficient_data",
      controlConverters: 0,
      minControlOrders: 100,
    } as any);

    vi.mocked(getCycleMetrics).mockResolvedValueOnce({
      hasSubscription: false,
    } as any);

    const homeData = await getHomeData("test.myshopify.com");

    expect(homeData).toHaveProperty("sync");
    expect(homeData.sync.productsTotal).toBe(50);
    expect(homeData.sync.productsActive).toBe(45);
    expect(homeData.sync.productsEmbedded).toBe(45);
  });
});
