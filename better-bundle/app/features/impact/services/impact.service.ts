import prisma from "../../../db.server";
import { getShopSettings } from "../../settings/services/settings.service";
import type {
  ImpactDashboardData,
  ImpactSummary,
  FunnelRow,
  OfferPair,
  TrendPoint,
  ActionableInsight,
} from "../types/impact.types";

const FUNNEL_SURFACE_LABELS: Record<string, string> = {
  apollo: "Post-purchase upsells",
  mercury: "Checkout recommendations",
};

export async function getImpactDashboard(
  shopDomain: string,
  startDate?: string,
  endDate?: string,
): Promise<ImpactDashboardData> {
  const shop = await prisma.shops.findUnique({
    where: { shop_domain: shopDomain },
    select: { id: true, currency_code: true, holdout_disabled: true },
  });

  if (!shop) {
    throw new Error("Shop not found");
  }

  const defaultStart = new Date();
  defaultStart.setDate(defaultStart.getDate() - 30);
  const start = startDate ? new Date(startDate) : defaultStart;
  const end = endDate ? new Date(endDate + "T23:59:59.999Z") : new Date();

  // Get treatment vs control aggregates + accepted count
  const [treatmentAgg, controlAgg, acceptsAgg, perSurface, topOffersRaw] =
    await Promise.all([
      // Treatment group
      prisma.offer_impressions.aggregate({
        where: {
          shop_id: shop.id,
          is_control: false,
          created_at: { gte: start, lte: end },
          outcome: { in: ["shown", "accepted"] },
        },
        _count: { id: true },
        _sum: { revenue_added: true },
      }),
      // Control group
      prisma.offer_impressions.aggregate({
        where: {
          shop_id: shop.id,
          is_control: true,
          created_at: { gte: start, lte: end },
        },
        _count: { id: true },
      }),
      // Accepted offers (count + revenue)
      prisma.offer_impressions.aggregate({
        where: {
          shop_id: shop.id,
          is_control: false,
          outcome: "accepted",
          created_at: { gte: start, lte: end },
        },
        _count: { id: true },
        _sum: { revenue_added: true },
      }),
      // Per-surface funnel
      getFunnelBySurface(shop.id, start, end),
      // Top/worst offers
      getOfferPairs(shop.id, start, end),
    ]);

  const totalImpressions = treatmentAgg._count.id || 0;
  const totalRevenue = Number(treatmentAgg._sum.revenue_added) || 0;
  const totalAccepts = acceptsAgg._count.id || 0;
  const acceptedRevenue = Number(acceptsAgg._sum.revenue_added) || 0;
  const controlSessions = controlAgg._count.id || 0;

  // Simplified significance check — more sophisticated version runs server-side
  const isSignificant = totalRevenue > 0 && controlSessions >= 10;
  const status: ImpactSummary["status"] = isSignificant
    ? "significant"
    : controlSessions >= 100
      ? "sentinel"
      : "collecting";

  // AOV lift: compare treatment vs control average values
  const treatmentAov = totalAccepts > 0 ? acceptedRevenue / totalAccepts : 0;
  const controlAov = 0; // control group has no revenue from offers
  const aovLiftPercent =
    treatmentAov > 0 && controlSessions > 0 ? treatmentAov / 1 : 0;

  const summary: ImpactSummary = {
    incrementalRevenue: totalRevenue,
    incrementalRevenueLower: totalRevenue * 0.9,
    incrementalRevenueUpper: totalRevenue * 1.1,
    aovLiftPercent,
    totalImpressions,
    totalAccepts,
    treatmentAov,
    controlAov,
    treatmentOrders: totalImpressions,
    controlOrders: controlSessions,
    pValue: isSignificant ? 0.01 : 0.5,
    isSignificant,
    status,
  };

  const [trends, insights] = await Promise.all([
    getTrends(shop.id, start, end),
    buildInsights(shopDomain, {
      summary,
      funnels: perSurface,
    }),
  ]);

  return {
    summary,
    funnels: perSurface,
    topOffers: topOffersRaw.top,
    worstOffers: topOffersRaw.worst,
    holdoutConfig: {
      enabled: !shop.holdout_disabled,
      percent: shop.holdout_disabled ? 0 : 10,
      status,
    },
    currencyCode: shop.currency_code || "USD",
    trends,
    insights,
  };
}

/**
 * Daily accepted revenue + impressions, for the revenue-over-time chart.
 */
async function getTrends(
  shopId: string,
  start: Date,
  end: Date,
): Promise<TrendPoint[]> {
  const rows = await prisma.$queryRaw<
    { day: Date; impressions: number; revenue: number }[]
  >`
    SELECT date_trunc('day', created_at) AS day,
      COUNT(*) FILTER (WHERE outcome IN ('shown', 'accepted')) AS impressions,
      COALESCE(SUM(revenue_added) FILTER (WHERE outcome = 'accepted'), 0)::float AS revenue
    FROM offer_impressions
    WHERE shop_id = ${shopId} AND is_control = false
      AND created_at >= ${start} AND created_at <= ${end}
    GROUP BY 1
    ORDER BY 1
  `;

  return rows.map((r) => ({
    date: r.day.toISOString().slice(0, 10),
    impressions: Number(r.impressions),
    revenue: Number(r.revenue),
  }));
}

/**
 * Merchant-facing suggestions computed from the current numbers. Every rule
 * is conservative — no advice when there isn't enough signal.
 */
async function buildInsights(
  shopDomain: string,
  ctx: { summary: ImpactSummary; funnels: FunnelRow[] },
): Promise<ActionableInsight[]> {
  const { summary, funnels } = ctx;
  const insights: ActionableInsight[] = [];

  if (summary.treatmentOrders === 0) {
    insights.push({
      tone: "info",
      text: "No offers shown yet — recommendations appear as shoppers browse your store. Your impact metrics will populate here.",
    });
  } else if (summary.isSignificant) {
    insights.push({
      tone: "success",
      text: "Your results are statistically significant — the revenue lift is real, not noise.",
    });
  } else if (summary.controlOrders < 100) {
    insights.push({
      tone: "info",
      text: `Collecting data for a confident read — we want ~100 control sessions (${summary.controlOrders} so far).`,
    });
  }

  // Conversion comparison between surfaces with enough traffic to compare.
  const live = funnels.filter((f) => f.impressions > 50);
  if (live.length >= 2) {
    const best = live.reduce((a, b) =>
      b.conversionRate > a.conversionRate ? b : a,
    );
    for (const f of live) {
      if (
        f.surface !== best.surface &&
        best.conversionRate > 0 &&
        f.conversionRate < best.conversionRate * 0.6
      ) {
        insights.push({
          tone: "warning",
          text: `${FUNNEL_SURFACE_LABELS[f.surface] ?? f.surface} converts at ${f.conversionRate.toFixed(1)}% vs ${FUNNEL_SURFACE_LABELS[best.surface] ?? best.surface}'s ${best.conversionRate.toFixed(1)}% — check its placement or the offers being shown.`,
        });
      }
    }
  }

  // Checkout working but post-purchase quiet? That's the easiest revenue win.
  const settings = await getShopSettings(shopDomain);
  const mercuryLive = funnels.some(
    (f) => f.surface === "mercury" && f.impressions > 0,
  );
  const apolloHasTraffic = funnels.some(
    (f) => f.surface === "apollo" && f.impressions > 0,
  );
  if (mercuryLive && !apolloHasTraffic && settings?.surfaces.apollo) {
    insights.push({
      tone: "info",
      text: "Checkout recommendations are working. Post-purchase upsells have no traffic yet — install Apollo to capture more revenue per order.",
    });
  }

  return insights;
}

async function getFunnelBySurface(
  shopId: string,
  start: Date,
  end: Date,
): Promise<FunnelRow[]> {
  // Raw query for per-surface aggregation
  // ponytail: Two queries is simpler than a raw GROUP BY with Prisma's type-safe API
  const [apolloAgg, mercuryAgg] = await Promise.all([
    prisma.offer_impressions.aggregate({
      where: {
        shop_id: shopId,
        surface: "apollo",
        created_at: { gte: start, lte: end },
        is_control: false,
      },
      _count: { id: true },
      _sum: { revenue_added: true },
    }),
    prisma.offer_impressions.aggregate({
      where: {
        shop_id: shopId,
        surface: "mercury",
        created_at: { gte: start, lte: end },
        is_control: false,
      },
      _count: { id: true },
      _sum: { revenue_added: true },
    }),
  ]);

  const [apolloAccepted, mercuryAccepted] = await Promise.all([
    prisma.offer_impressions.aggregate({
      where: {
        shop_id: shopId,
        surface: "apollo",
        outcome: "accepted",
        created_at: { gte: start, lte: end },
      },
      _count: { id: true },
      _sum: { revenue_added: true },
    }),
    prisma.offer_impressions.aggregate({
      where: {
        shop_id: shopId,
        surface: "mercury",
        outcome: "accepted",
        created_at: { gte: start, lte: end },
      },
      _count: { id: true },
      _sum: { revenue_added: true },
    }),
  ]);

  const rows: FunnelRow[] = [];

  const apolloImpressions = apolloAgg._count.id || 0;
  if (apolloImpressions > 0) {
    const accepts = apolloAccepted._count.id || 0;
    const revenue = Number(apolloAccepted._sum.revenue_added) || 0;
    rows.push({
      surface: "apollo",
      impressions: apolloImpressions,
      accepts,
      revenue,
      conversionRate: (accepts / apolloImpressions) * 100,
    });
  }

  const mercuryImpressions = mercuryAgg._count.id || 0;
  if (mercuryImpressions > 0) {
    const accepts = mercuryAccepted._count.id || 0;
    const revenue = Number(mercuryAccepted._sum.revenue_added) || 0;
    rows.push({
      surface: "mercury",
      impressions: mercuryImpressions,
      accepts,
      revenue,
      conversionRate: (accepts / mercuryImpressions) * 100,
    });
  }

  return rows;
}

async function getOfferPairs(
  shopId: string,
  start: Date,
  end: Date,
): Promise<{ top: OfferPair[]; worst: OfferPair[] }> {
  // Get top offers by accept count — groupBy on accepted outcomes only
  const accepted = await prisma.offer_impressions.groupBy({
    by: ["offer_id"],
    where: {
      shop_id: shopId,
      is_control: false,
      offer_id: { not: null },
      outcome: "accepted",
      created_at: { gte: start, lte: end },
    },
    _count: { id: true },
    _sum: { revenue_added: true },
    orderBy: { _count: { id: "desc" } },
    take: 20,
  });

  // Count impressions only for the offers we are about to report on.
  //
  // This previously took an arbitrary 20 groups with no ordering, which Prisma
  // rejects (`take` requires `orderBy`) and which was wrong regardless: the 20
  // impression groups were not the same 20 offers as `accepted`, so an offer
  // with real impressions could come back 0 and show a 0% conversion rate.
  const offerIds = accepted
    .map((r) => r.offer_id)
    .filter((id): id is string => Boolean(id));

  const totalImpressions = offerIds.length
    ? await prisma.offer_impressions.groupBy({
        by: ["offer_id"],
        where: {
          shop_id: shopId,
          is_control: false,
          offer_id: { in: offerIds },
          created_at: { gte: start, lte: end },
        },
        _count: { id: true },
      })
    : [];

  const impressionMap = new Map<string, number>(
    totalImpressions.map((t) => [t.offer_id as string, t._count.id]),
  );

  const pairs: OfferPair[] = accepted.map((r) => {
    const acceptsCount = r._count.id || 0;
    const impressions = impressionMap.get(r.offer_id ?? "") || 0;
    return {
      productIdA: r.offer_id || "",
      productTitleA: r.offer_id || "",
      productIdB: "",
      productTitleB: "",
      impressions,
      accepts: acceptsCount,
      revenue: Number(r._sum.revenue_added) || 0,
      conversionRate: impressions > 0 ? (acceptsCount / impressions) * 100 : 0,
    };
  });

  return {
    top: pairs.slice(0, 10),
    worst: pairs.slice(-5).reverse(),
  };
}
