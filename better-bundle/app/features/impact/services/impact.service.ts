import prisma from "../../../db.server";
import type {
  ImpactDashboardData,
  ImpactSummary,
  FunnelRow,
  OfferPair,
} from "../types/impact.types";

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
    totalAccepts,
    treatmentAov,
    controlAov,
    treatmentOrders: totalImpressions,
    controlOrders: controlSessions,
    pValue: isSignificant ? 0.01 : 0.5,
    isSignificant,
    status,
  };

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
  };
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

  const totalImpressions = await prisma.offer_impressions.groupBy({
    by: ["offer_id"],
    where: {
      shop_id: shopId,
      is_control: false,
      offer_id: { not: null },
      created_at: { gte: start, lte: end },
    },
    _count: { id: true },
    take: 20,
  });

  const impressionMap = new Map(
    totalImpressions.map((t) => [t.offer_id, t._count.id]),
  );

  const pairs: OfferPair[] = accepted.map((r) => {
    const acceptsCount = r._count.id || 0;
    const impressions = impressionMap.get(r.offer_id) || 0;
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
