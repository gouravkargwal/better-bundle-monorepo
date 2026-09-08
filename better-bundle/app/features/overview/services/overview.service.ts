// features/overview/services/overview.service.ts
//
// Aggregates everything the /app/overview dashboard needs:
//  - headline KPIs (reused from the impact service)
//  - edge-pipeline health from the worker (servable? products? edges?)
//  - per-surface serving status (settings flags + impression data)
//  - top recommended products by accepted revenue
import prisma from "../../../db.server";
import { getImpactDashboard } from "../../impact/services/impact.service";
import { getShopSettings } from "../../settings/services/settings.service";
import type {
  EdgeStatus,
  OverviewData,
  SurfaceStatus,
  TopProduct,
  SurfaceKey,
} from "../types/overview.types";

const SURFACES: { key: SurfaceKey; label: string; emoji: string }[] = [
  { key: "mercury", label: "Checkout", emoji: "🛒" },
  { key: "apollo", label: "Post-purchase", emoji: "⚡" },
  { key: "thank_you", label: "Thank-you page", emoji: "🎉" },
  { key: "phoenix", label: "Storefront", emoji: "🏪" },
  { key: "venus", label: "Customer account", emoji: "👤" },
];

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

export async function getOverviewData(
  shopDomain: string,
): Promise<OverviewData> {
  const [settings, impact] = await Promise.all([
    getShopSettings(shopDomain),
    getImpactDashboard(shopDomain),
  ]);
  if (!settings) {
    throw new Error("Shop not found");
  }

  const shopId = settings.shopId;
  const [edges, surfaceStats, topProducts] = await Promise.all([
    getEdgeStatus(shopId),
    getSurfaceStats(shopId),
    getTopProducts(shopId),
  ]);

  const surfaces: SurfaceStatus[] = SURFACES.map((surface) => {
    const stats = surfaceStats.get(surface.key);
    const enabled = settings.surfaces[surface.key];
    const impressions = Number(stats?.impressions) || 0;
    return {
      key: surface.key,
      label: surface.label,
      emoji: surface.emoji,
      enabled,
      impressions,
      accepts: Number(stats?.accepts) || 0,
      revenue: Number(stats?.revenue) || 0,
      status: !enabled ? "disabled" : impressions > 0 ? "live" : "no_traffic",
    };
  });

  return {
    impact,
    edges,
    surfaces,
    topProducts,
    shopCurrency: settings.shopCurrency,
  };
}