import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../../../shopify.server";
import { getDateRangeFromUrl } from "../../../utils/datetime";
import prisma from "../../../db.server";

export async function loadRevenueData({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const url = new URL(request.url);
  const { startDate, endDate } = getDateRangeFromUrl(url);

  try {
    // Get shop info
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: session.shop },
      select: { id: true, currency_code: true, money_format: true },
    });

    if (!shop) {
      return json({ error: "Shop not found" }, { status: 404 });
    }

    // Parse dates
    const start = new Date(startDate + "T00:00:00.000Z");
    const end = new Date(endDate + "T23:59:59.999Z");

    // Get revenue-specific data only
    const [overview, attributedMetrics] = await Promise.all([
      getRevenueOverview(
        shop.id,
        start,
        end,
        shop.currency_code || "USD",
        shop.money_format || "{{amount}}",
      ),
      getAttributedMetrics(shop.id, start, end, shop.currency_code || "USD"),
    ]);

    return json({
      overview,
      attributedMetrics,
      startDate,
      endDate,
    });
  } catch (error) {
    console.error("Revenue data error:", error);
    return json({ error: "Failed to load revenue data" }, { status: 500 });
  }
}

async function getRevenueOverview(
  shopId: string,
  startDate: Date,
  endDate: Date,
  currencyCode: string,
  moneyFormat: string,
) {
  // Get current period metrics
  const currentMetrics = await getMetricsForPeriod(shopId, startDate, endDate);

  // Get previous period for comparison
  const periodDuration = endDate.getTime() - startDate.getTime();
  const previousEndDate = new Date(startDate.getTime() - 1);
  const previousStartDate = new Date(
    previousEndDate.getTime() - periodDuration,
  );
  const previousMetrics = await getMetricsForPeriod(
    shopId,
    previousStartDate,
    previousEndDate,
  );

  const conversionRate =
    currentMetrics.clicks > 0
      ? (currentMetrics.clicks / currentMetrics.views) * 100
      : 0;
  const previousConversionRate =
    previousMetrics.clicks > 0
      ? (previousMetrics.clicks / previousMetrics.views) * 100
      : 0;

  return {
    total_revenue: currentMetrics.revenue,
    conversion_rate: Math.round(conversionRate * 10) / 10,
    total_recommendations: currentMetrics.views,
    total_clicks: currentMetrics.clicks,
    average_order_value: currentMetrics.averageOrderValue,
    period: "custom",
    currency_code: currencyCode,
    money_format: moneyFormat,
    revenue_change: calculatePercentageChange(
      currentMetrics.revenue,
      previousMetrics.revenue,
    ),
    conversion_rate_change: calculatePercentageChange(
      conversionRate,
      previousConversionRate,
    ),
    recommendations_change: calculatePercentageChange(
      currentMetrics.views,
      previousMetrics.views,
    ),
    clicks_change: calculatePercentageChange(
      currentMetrics.clicks,
      previousMetrics.clicks,
    ),
    aov_change: calculatePercentageChange(
      currentMetrics.averageOrderValue,
      previousMetrics.averageOrderValue,
    ),
    total_customers: currentMetrics.customers,
    customers_change: calculatePercentageChange(
      currentMetrics.customers,
      previousMetrics.customers,
    ),
  };
}

async function getMetricsForPeriod(
  shopId: string,
  startDate: Date,
  endDate: Date,
) {
  const [viewCount, clickCount, purchasesAgg, customerCount] =
    await Promise.all([
      prisma.user_interactions.count({
        where: {
          shop_id: shopId,
          created_at: { gte: startDate, lte: endDate },
          interaction_type: {
            in: ["recommendation_viewed", "product_viewed", "page_viewed"],
          },
        },
      }),
      prisma.user_interactions.count({
        where: {
          shop_id: shopId,
          created_at: { gte: startDate, lte: endDate },
          interaction_type: {
            in: ["recommendation_add_to_cart", "product_added_to_cart"],
          },
        },
      }),
      prisma.purchase_attributions.aggregate({
        where: {
          shop_id: shopId,
          purchase_at: { gte: startDate, lte: endDate },
        },
        _sum: { total_revenue: true },
        _avg: { total_revenue: true },
      }),
      prisma.user_sessions
        .groupBy({
          by: ["customer_id"],
          where: {
            shop_id: shopId,
            created_at: { gte: startDate, lte: endDate },
            customer_id: { not: null },
          },
        })
        .then((result) => result.length),
    ]);

  const revenue = Number(purchasesAgg._sum.total_revenue) || 0;
  return {
    views: viewCount,
    clicks: clickCount,
    revenue,
    averageOrderValue: Number(purchasesAgg._avg.total_revenue) || 0,
    customers: customerCount,
  };
}

async function getAttributedMetrics(
  shopId: string,
  startDate: Date,
  endDate: Date,
  currencyCode: string,
) {
  const [attributedRevenueData, totalRevenueData] = await Promise.all([
    prisma.purchase_attributions.aggregate({
      where: { shop_id: shopId, purchase_at: { gte: startDate, lte: endDate } },
      _sum: { total_revenue: true },
    }),
    prisma.order_data.aggregate({
      where: { shop_id: shopId, order_date: { gte: startDate, lte: endDate } },
      _sum: { total_amount: true },
    }),
  ]);

  const attributedRevenue =
    Number(attributedRevenueData._sum.total_revenue) || 0;
  const totalRevenue = Number(totalRevenueData._sum.total_amount) || 0;
  const attributionRate =
    totalRevenue > 0 ? (attributedRevenue / totalRevenue) * 100 : 0;

  return {
    attributed_revenue: attributedRevenue,
    attributed_refunds: 0,
    net_attributed_revenue: attributedRevenue,
    attribution_rate: Math.round(attributionRate * 100) / 100,
    refund_rate: 0,
    currency_code: currencyCode,
  };
}

function calculatePercentageChange(
  current: number,
  previous: number,
): number | null {
  if (previous === 0) return null;
  return Math.round(((current - previous) / previous) * 100 * 10) / 10;
}
