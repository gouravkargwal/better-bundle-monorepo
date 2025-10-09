import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../../../shopify.server";
import { getDateRangeFromUrl } from "../../../utils/datetime";
import prisma from "../../../db.server";

export async function loadActivityData({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const url = new URL(request.url);
  const { startDate, endDate } = getDateRangeFromUrl(url);

  try {
    // Get shop info
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: session.shop },
      select: { id: true, currency_code: true },
    });

    if (!shop) {
      return json({ error: "Shop not found" }, { status: 404 });
    }

    // Parse dates
    const start = new Date(startDate + "T00:00:00.000Z");
    const end = new Date(endDate + "T23:59:59.999Z");

    // Get activity-specific data only
    const recentActivity = await getRecentActivityData(
      shop.id,
      start,
      end,
      shop.currency_code || "USD",
    );

    return json({
      recentActivity,
      startDate,
      endDate,
    });
  } catch (error) {
    console.error("Activity data error:", error);
    return json({ error: "Failed to load activity data" }, { status: 500 });
  }
}

async function getRecentActivityData(
  shopId: string,
  startDate: Date,
  endDate: Date,
  currencyCode: string,
) {
  try {
    const { todayStart, yesterdayStart, thisWeekStart } =
      getActivityDateRanges();

    const [todayMetrics, yesterdayMetrics, thisWeekMetrics] = await Promise.all(
      [
        getActivityMetrics(shopId, todayStart, endDate),
        getActivityMetrics(shopId, yesterdayStart, todayStart),
        getActivityMetrics(shopId, thisWeekStart, endDate),
      ],
    );

    return {
      today: todayMetrics,
      yesterday: yesterdayMetrics,
      this_week: thisWeekMetrics,
      currency_code: currencyCode,
    };
  } catch (error) {
    console.error("Failed to get recent activity:", error);
    return {
      today: { recommendations: 0, clicks: 0, revenue: 0, customers: 0 },
      yesterday: { recommendations: 0, clicks: 0, revenue: 0, customers: 0 },
      this_week: { recommendations: 0, clicks: 0, revenue: 0, customers: 0 },
      currency_code: currencyCode,
    };
  }
}

function getActivityDateRanges() {
  const now = new Date();
  const todayStart = new Date(now);
  todayStart.setHours(0, 0, 0, 0);

  const yesterdayStart = new Date(todayStart);
  yesterdayStart.setDate(yesterdayStart.getDate() - 1);

  const thisWeekStart = new Date(todayStart);
  thisWeekStart.setDate(thisWeekStart.getDate() - 7);

  return { todayStart, yesterdayStart, thisWeekStart };
}

async function getActivityMetrics(
  shopId: string,
  startDate: Date,
  endDate: Date,
): Promise<{
  recommendations: number;
  clicks: number;
  revenue: number;
  customers: number;
}> {
  const [recommendations, clicks, revenue, customers] = await Promise.all([
    prisma.user_interactions.count({
      where: {
        shop_id: shopId,
        created_at: { gte: startDate, lte: endDate },
        interaction_type: { in: ["recommendation_viewed", "product_viewed"] },
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
    prisma.purchase_attributions
      .aggregate({
        where: {
          shop_id: shopId,
          purchase_at: { gte: startDate, lte: endDate },
        },
        _sum: { total_revenue: true },
      })
      .then((result) => Number(result._sum.total_revenue) || 0),
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
    recommendations: Number(recommendations),
    clicks: Number(clicks),
    revenue: Number(revenue),
    customers: Number(customers),
  };
}
