// features/overview/services/home.service.ts
//
// Aggregates everything the Home page (/app/overview) needs:
//  - the incrementality result, as a state, from the statistics engine
//  - edge-pipeline health from the worker (servable? products? edges?)
//  - per-surface serving status (settings flags + impression data)
//  - top recommended products by accepted revenue
import prisma from "../../../db.server";
import { getLiftSummary } from "../../impact/services/lift.service";
import { getShopSettings } from "../../settings/services/settings.service";
import { getCycleMetrics } from "./cycle.service";
import { ALL_SURFACES } from "../../../lib/surfaces";
import { holdoutPercentFor } from "../../../lib/holdout";
import type {
  EdgeStatus,
  HomeData,
  SurfaceStatus,
  TopProduct,
  SurfaceKey,
  SurfaceLiveStatus,
  SyncStatus,
} from "../types/home.types";

// Placements come from the shared registry rather than a local copy. This
// array was the third competing definition of the five surfaces — with its own
// labels and emoji — alongside settings.types.ts and the impact service's
// two-entry map. One registry means a placement cannot be labelled two ways or
// silently omitted from a list.

export async function getEdgeStatus(shopId: string): Promise<EdgeStatus> {
  const backendUrl = process.env.PYTHON_WORKER_API_URL;
  const unavailable: EdgeStatus = {
    reachable: false,
    servable: false,
    products: 0,
    totalEdges: 0,
    observedEdges: 0,
  };
  if (!backendUrl) return unavailable;

  try {
    // 8s, raised from 4s. This is an admin page load, not a shopper-facing
    // request, so a slow answer is far better than a warning banner claiming
    // the engine is unreachable when it is merely busy or behind a dev tunnel.
    // A false "can't reach the recommendation engine" sends you debugging the
    // wrong system entirely.
    const response = await fetch(
      `${backendUrl}/api/v1/edges/status/${shopId}`,
      { signal: AbortSignal.timeout(8_000) },
    );
    if (!response.ok) return unavailable;
    const data = await response.json();
    return {
      reachable: true,
      servable: data?.servable === true,
      products: Number(data?.products) || 0,
      totalEdges: Number(data?.total_edges) || 0,
      observedEdges: Number(data?.observed_edges) || 0,
    };
  } catch {
    return unavailable;
  }
}

interface SyncStatusRow {
  products_total: number;
  products_active: number;
  products_embedded: number;
  products_in_store: number | null;
  collections_total: number;
  orders_total: number;
  edges_total: number;
  edges_observed: number;
  last_synced_at: Date | string | null;
}

export async function getSyncStatus(shopId: string): Promise<SyncStatus> {
  const fallback: SyncStatus = {
    productsTotal: 0,
    productsActive: 0,
    productsEmbedded: 0,
    productsInStore: null,
    collectionsTotal: 0,
    ordersTotal: 0,
    edgesTotal: 0,
    edgesObserved: 0,
    lastSyncedAt: null,
  };

  try {
    const rows = await prisma.$queryRaw<SyncStatusRow[]>`
      SELECT
        (SELECT COUNT(*)::int FROM product_data WHERE shop_id = ${shopId}) AS products_total,
        (SELECT COUNT(*)::int FROM product_data WHERE shop_id = ${shopId} AND is_active = true) AS products_active,
        (SELECT COUNT(*)::int FROM product_vectors WHERE shop_id = ${shopId}) AS products_embedded,
        (SELECT (settings -> 'catalog_totals' ->> 'products')::int FROM shops WHERE id = ${shopId}) AS products_in_store,
        (SELECT COUNT(*)::int FROM collection_data WHERE shop_id = ${shopId}) AS collections_total,
        (SELECT COUNT(*)::int FROM order_data WHERE shop_id = ${shopId}) AS orders_total,
        (SELECT COUNT(*)::int FROM product_edges WHERE shop_id = ${shopId}) AS edges_total,
        (SELECT COUNT(*)::int FROM product_edges WHERE shop_id = ${shopId} AND observed_count > 0) AS edges_observed,
        GREATEST(
          (SELECT MAX(updated_at) FROM product_data WHERE shop_id = ${shopId}),
          (SELECT MAX(updated_at) FROM collection_data WHERE shop_id = ${shopId}),
          (SELECT MAX(updated_at) FROM order_data WHERE shop_id = ${shopId})
        ) AS last_synced_at
    `;

    if (!rows || rows.length === 0) {
      return fallback;
    }

    const row = rows[0];
    let lastSyncedAt: string | null = null;
    if (row.last_synced_at) {
      const d = new Date(row.last_synced_at);
      if (!isNaN(d.getTime())) {
        lastSyncedAt = d.toISOString();
      }
    }

    return {
      productsTotal: Number(row.products_total) || 0,
      productsActive: Number(row.products_active) || 0,
      productsEmbedded: Number(row.products_embedded) || 0,
      productsInStore:
        row.products_in_store == null ? null : Number(row.products_in_store),
      collectionsTotal: Number(row.collections_total) || 0,
      ordersTotal: Number(row.orders_total) || 0,
      edgesTotal: Number(row.edges_total) || 0,
      edgesObserved: Number(row.edges_observed) || 0,
      lastSyncedAt,
    };
  } catch {
    return fallback;
  }
}

interface SurfaceStatsRow {
  surface: string;
  impressions: number;
  accepts: number;
  revenue: number;
}

async function getSurfaceStats(shopId: string): Promise<Map<string, SurfaceStatsRow>> {
  const [impressionRows, revenueRows] = await Promise.all([
    prisma.$queryRaw<SurfaceStatsRow[]>`
      SELECT surface,
        COUNT(*) FILTER (WHERE outcome IN ('shown', 'accepted')) AS impressions,
        COUNT(*) FILTER (WHERE paid IS TRUE) AS accepts,
        0::float AS revenue
      FROM offer_impressions
      WHERE shop_id = ${shopId} AND is_control = false
      GROUP BY surface
    `,
    prisma.$queryRaw<{ surface: string; revenue: number }[]>`
      SELECT key AS surface,
        COALESCE(SUM((pa.attributed_revenue::text::json->>key)::numeric), 0)::float AS revenue
      FROM purchase_attributions pa,
        LATERAL json_object_keys(pa.attributed_revenue::text::json) AS key(surface)
      WHERE pa.shop_id = ${shopId}
        AND key != 'total'
      GROUP BY key
    `,
  ]);

  const revenueBySurface = new Map(revenueRows.map((r) => [r.surface, r.revenue]));
  return new Map(
    impressionRows.map((r) => [
      r.surface,
      { ...r, revenue: revenueBySurface.get(r.surface) ?? 0 },
    ])
  );
}

interface TopOfferRow {
  offer_id: string;
  accepts: number;
  revenue: number;
}

export async function getTopProducts(
  shopId: string,
  limit = 6,
): Promise<TopProduct[]> {
  const rows = await prisma.$queryRaw<TopOfferRow[]>`
    SELECT offer_id, COUNT(*) AS accepts, COALESCE(SUM(revenue_added), 0)::float AS revenue
    FROM offer_impressions
    WHERE shop_id = ${shopId} AND is_control = false
      AND paid IS TRUE AND offer_id IS NOT NULL
    GROUP BY offer_id
    ORDER BY revenue DESC
    LIMIT ${limit}
  `;
  if (rows.length === 0) return [];

  const productRows = await prisma.product_data.findMany({
    where: {
      shop_id: shopId,
      product_id: { in: rows.map((r) => r.offer_id) },
    },
    select: { product_id: true, title: true, images: true, price: true },
  });
  const byId = new Map(productRows.map((p) => [p.product_id, p]));

  return rows.map((r) => {
    const product = byId.get(r.offer_id);
    const images =
      (product?.images as Array<Record<string, unknown>> | null) ?? [];
    const firstImage = images[0] as { url?: string } | undefined;
    return {
      productId: r.offer_id,
      title: product?.title ?? r.offer_id,
      imageUrl: firstImage?.url ?? null,
      price: product?.price ?? null,
      accepts: Number(r.accepts),
      revenue: Number(r.revenue),
    };
  });
}

export async function getHomeData(
  shopDomain: string,
): Promise<HomeData> {
  const settings = await getShopSettings(shopDomain);
  if (!settings) {
    throw new Error("Shop not found");
  }

  const shopId = settings.shopId;
  // The incrementality claim comes from the statistics engine as a state, not
  // as a number this page can invent. Everything else here is deterministic
  // and read straight from Postgres, so the page still renders in full if the
  // worker is unreachable.
  const [edges, sync, surfaceStats, topProducts, proof, cycle] = await Promise.all([
    getEdgeStatus(shopId),
    getSyncStatus(shopId),
    getSurfaceStats(shopId),
    getTopProducts(shopId),
    getLiftSummary(shopId),
    // Read from the billing tables the charge is computed from, so the figure
    // on this page and the figure on the invoice cannot diverge.
    getCycleMetrics(shopId),
  ]);

  const surfaces: SurfaceStatus[] = ALL_SURFACES.map((surface) => {
    const stats = surfaceStats.get(surface.key);
    const enabled = settings.surfaces[surface.key];
    const impressions = Number(stats?.impressions) || 0;
    const isDetected = settings.detectedSurfaces?.[surface.key];

    let status: SurfaceLiveStatus;
    if (!enabled) {
      status = "disabled";
    } else if (impressions > 0) {
      status = "live";
    } else if (isDetected === false) {
      status = "not_installed";
    } else {
      // Either confirmed installed via App Bridge (isDetected === true)
      // or pending first traffic/detection. Awaiting traffic avoids falsely accusing
      // the merchant of not installing a block they already placed.
      status = "awaiting_traffic";
    }

    return {
      key: surface.key,
      label: surface.label,
      enabled,
      installed: isDetected ?? undefined,
      impressions,
      accepts: Number(stats?.accepts) || 0,
      revenue: Number(stats?.revenue) || 0,
      status,
    };
  });

  return {
    cycle,
    proof,
    holdoutPercent: holdoutPercentFor({
      holdout_disabled: settings.holdoutDisabled,
      holdout_percent: settings.holdoutPercent,
    }),
    edges,
    sync,
    surfaces,
    topProducts,
    shopCurrency: settings.shopCurrency,
  };
}