import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../../../shopify.server";
import { getDateRangeFromUrl } from "../../../utils/datetime";
import prisma from "../../../db.server";

export async function loadPerformanceData({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const url = new URL(request.url);
  const { startDate, endDate } = getDateRangeFromUrl(url);

  try {
    // Get shop info
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: session.shop },
      select: { id: true },
    });

    if (!shop) {
      return json({ error: "Shop not found" }, { status: 404 });
    }

    // Parse dates
    const start = new Date(startDate + "T00:00:00.000Z");
    const end = new Date(endDate + "T23:59:59.999Z");

    // Get performance-specific data only
    const performance = await getPerformanceMetrics(shop.id, start, end);

    return json({
      performance,
      startDate,
      endDate,
    });
  } catch (error) {
    console.error("Performance data error:", error);
    return json({ error: "Failed to load performance data" }, { status: 500 });
  }
}

async function getPerformanceMetrics(
  shopId: string,
  startDate: Date,
  endDate: Date,
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

  const currentConversionRate =
    currentMetrics.clicks > 0
      ? (currentMetrics.clicks / currentMetrics.views) * 100
      : 0;
  const previousConversionRate =
    previousMetrics.clicks > 0
      ? (previousMetrics.clicks / previousMetrics.views) * 100
      : 0;

  return {
    total_recommendations: currentMetrics.views,
    total_clicks: currentMetrics.clicks,
    conversion_rate: Math.round(currentConversionRate * 10) / 10,
    total_customers: currentMetrics.customers,
    recommendations_change: calculatePercentageChange(
      currentMetrics.views,
      previousMetrics.views,
    ),
    clicks_change: calculatePercentageChange(
      currentMetrics.clicks,
      previousMetrics.clicks,
    ),
    conversion_rate_change: calculatePercentageChange(
      currentConversionRate,
      previousConversionRate,
    ),
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
  const [viewCount, clickCount, customerCount] = await Promise.all([
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

  return {
    views: viewCount,
    clicks: clickCount,
    customers: customerCount,
  };
}

function calculatePercentageChange(
  current: number,
  previous: number,
): number | null {
  if (previous === 0) return null;
  return Math.round(((current - previous) / previous) * 100 * 10) / 10;
}
