import { describe, it, expect } from "vitest";
import {
  getSyncStatusBadge,
  formatLastSynced,
} from "../SyncStatusCard";
import type { SyncStatus } from "../../types/home.types";

describe("SyncStatusCard helpers", () => {
  const baseSync: SyncStatus = {
    productsTotal: 100,
    productsActive: 90,
    productsEmbedded: 90,
    productsInStore: 100,
    collectionsTotal: 10,
    ordersTotal: 500,
    edgesTotal: 200,
    edgesObserved: 50,
    lastSyncedAt: "2026-09-13T10:00:00.000Z",
  };

  describe("getSyncStatusBadge", () => {
    it("returns 'Awaiting initial sync' when store has no products and no orders", () => {
      const badge = getSyncStatusBadge({
        ...baseSync,
        productsTotal: 0,
        productsActive: 0,
        productsEmbedded: 0,
        ordersTotal: 0,
      });
      expect(badge.label).toBe("Awaiting initial sync");
      expect(badge.tone).toBe("attention");
    });

    it("returns 'Indexing in progress' when products are active but embeddings are incomplete", () => {
      const badge = getSyncStatusBadge({
        ...baseSync,
        productsActive: 90,
        productsEmbedded: 45,
      });
      expect(badge.label).toBe("Indexing in progress");
      expect(badge.tone).toBe("attention");
    });

    it("flags an incomplete catalog even when everything imported is embedded", () => {
      // The regression this guards: 251 of 997 products imported, all of them
      // embedded, and every figure on the card read 100% because the
      // denominator was our own import count.
      const badge = getSyncStatusBadge({
        ...baseSync,
        productsTotal: 251,
        productsActive: 251,
        productsEmbedded: 251,
        productsInStore: 997,
      });
      expect(badge.label).toBe("Catalog sync incomplete");
      expect(badge.tone).toBe("attention");
    });

    it("returns 'Up to date' when the store count is not yet known", () => {
      const badge = getSyncStatusBadge({ ...baseSync, productsInStore: null });
      expect(badge.label).toBe("Up to date");
    });

    it("returns 'Up to date' when active products are fully embedded", () => {
      const badge = getSyncStatusBadge({
        ...baseSync,
        productsActive: 90,
        productsEmbedded: 90,
      });
      expect(badge.label).toBe("Up to date");
      expect(badge.tone).toBe("success");
    });
  });

  describe("formatLastSynced", () => {
    it("returns 'Awaiting initial sync' for null timestamp", () => {
      expect(formatLastSynced(null)).toBe("Awaiting initial sync");
    });

    it("returns 'Awaiting initial sync' for invalid timestamp string", () => {
      expect(formatLastSynced("invalid-date")).toBe("Awaiting initial sync");
    });

    it("formats today's timestamp as 'Last updated: Today at ...'", () => {
      const now = new Date("2026-09-13T14:30:00.000Z");
      const result = formatLastSynced("2026-09-13T10:15:00.000Z", now);
      expect(result).toMatch(/^Last updated: Today at /);
    });

    it("formats older timestamp with date and time", () => {
      const now = new Date("2026-09-13T14:30:00.000Z");
      const result = formatLastSynced("2026-09-10T08:00:00.000Z", now);
      expect(result).toMatch(/^Last updated: Sep 10 at /);
    });
  });
});
