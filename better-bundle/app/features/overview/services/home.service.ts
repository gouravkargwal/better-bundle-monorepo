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
import type {
  EdgeStatus,
  HomeData,
  SurfaceStatus,
  TopProduct,
  SurfaceKey,
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
    const response = await fetch(
      `${backendUrl}/api/v1/edges/status/${shopId}`,
      { signal: AbortSignal.timeout(4_000) },
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

interface SurfaceStatsRow {
  surface: string;
  impressions: number;
  accepts: number;
  revenue: number;
}

async function getSurfaceStats(shopId: string): Promise<Map<string, SurfaceStatsRow>> {
  const rows = await prisma.$queryRaw<SurfaceStatsRow[]>`
    SELECT surface,
      COUNT(*) FILTER (WHERE outcome IN ('shown', 'accepted')) AS impressions,
      COUNT(*) FILTER (WHERE outcome = 'accepted') AS accepts,
      COALESCE(SUM(revenue_added) FILTER (WHERE outcome = 'accepted'), 0)::float AS revenue
    FROM offer_impressions
    WHERE shop_id = ${shopId} AND is_control = false
    GROUP BY surface
  `;
  return new Map(rows.map((r) => [r.surface, r]));
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
      AND outcome = 'accepted' AND offer_id IS NOT NULL
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
  const [edges, surfaceStats, topProducts, proof, cycle] = await Promise.all([
    getEdgeStatus(shopId),
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
    holdoutPercent: settings.holdoutDisabled ? 0 : 10,
    edges,
    surfaces,
    topProducts,
    shopCurrency: settings.shopCurrency,
  };
}