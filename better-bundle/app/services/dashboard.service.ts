import prisma from "../db.server";
import { getCacheService, CacheKeys, CacheTTL } from "./redis.service";

export interface DashboardOverview {
  total_revenue: number;
  conversion_rate: number;
  total_recommendations: number;
  total_clicks: number;
  average_order_value: number;
  period: string;
  currency_code: string;
  money_format: string;
  // Period-over-period changes (null for first period)
  revenue_change: number | null;
  conversion_rate_change: number | null;
  recommendations_change: number | null;
  clicks_change: number | null;
  aov_change: number | null;
  // SIMPLIFIED: Only show what store owners care about
  total_customers: number;
  customers_change: number | null;
}

export interface TopProductData {
  product_id: string;
  title: string;
  revenue: number;
  clicks: number;
  conversion_rate: number;
  recommendations_shown: number;
  currency_code: string;
  // SIMPLIFIED: Only show what matters for product decisions
  customers: number;
}

export interface RecentActivityData {
  today: {
    recommendations: number;
    clicks: number;
    revenue: number;
    customers: number;
  };
  yesterday: {
    recommendations: number;
    clicks: number;
    revenue: number;
    customers: number;
  };
  this_week: {
    recommendations: number;
    clicks: number;
    revenue: number;
    customers: number;
  };
  currency_code: string;
}

export interface AttributedMetrics {
  attributed_revenue: number;
  attributed_refunds: number;
  net_attributed_revenue: number;
  attribution_rate: number;
  refund_rate: number;
  currency_code: string;
}

export interface DashboardData {
  overview: DashboardOverview;
  topProducts: TopProductData[];
  recentActivity: RecentActivityData;
  attributedMetrics: AttributedMetrics;
}

async function getShopInfo(shopDomain: string): Promise<{
  id: string;
  currency_code: string;
  money_format: string;
}> {
  const cache = await getCacheService();
  const cacheKey = CacheKeys.shop(shopDomain);

  return await cache.getOrSet(
    cacheKey,
    async () => {
      const shop = await prisma.shops.findUnique({
        where: { shop_domain: shopDomain },
        select: {
          id: true,
          currency_code: true,
          money_format: true,
        },
      });

      if (!shop) {
        throw new Error(`Shop not found: ${shopDomain}`);
      }

      return {
        id: shop.id,
        currency_code: shop.currency_code || "USD",
        money_format: shop.money_format || "${{amount}}",
      };
    },
    CacheTTL.SHOP,
  );
}

function getDatesForPeriod(
  period: "last_30_days" | "last_7_days" | "today" = "last_30_days",
) {
  const endDate = new Date();
  const startDate = new Date();

  switch (period) {
    case "today":
      startDate.setHours(0, 0, 0, 0);
      break;
    case "last_7_days":
      startDate.setDate(endDate.getDate() - 7);
      break;
    case "last_30_days":
    default:
      startDate.setDate(endDate.getDate() - 30);
      break;
  }

  return { startDate, endDate };
}

export async function getDashboardOverview(
  shopDomain: string,
  period: "last_30_days" | "last_7_days" | "today" = "last_30_days",
): Promise<DashboardData> {
  const shopInfo = await getShopInfo(shopDomain);
  const { startDate, endDate } = getDatesForPeriod(period);

  const cache = await getCacheService();
  const cacheKey = CacheKeys.dashboard(
    shopInfo.id,
    period,
    startDate.toISOString(),
    endDate.toISOString(),
  );

  return await cache.getOrSet(
    cacheKey,
    async () => {
      // Execute all queries in parallel for maximum performance
      const [overview, topProducts, recentActivity, attributedMetrics] =
        await Promise.all([
          getOverviewMetrics(
            shopInfo.id,
            startDate,
            endDate,
            shopInfo.currency_code,
            shopInfo.money_format,
          ),
          getTopProducts(
            shopInfo.id,
            startDate,
            endDate,
            10,
            shopInfo.currency_code,
          ),
          getRecentActivity(
            shopInfo.id,
            startDate,
            endDate,
            shopInfo.currency_code,
          ),
          getAttributedMetrics(
            shopInfo.id,
            startDate,
            endDate,
            shopInfo.currency_code,
          ),
        ]);

      return {
        overview,
        topProducts,
        recentActivity,
        attributedMetrics,
      };
    },
    CacheTTL.DASHBOARD,
  );
}

async function getOverviewMetrics(
  shopId: string,
  startDate: Date,
  endDate: Date,
  currencyCode: string,
  moneyFormat: string,
): Promise<DashboardOverview> {
  const cache = await getCacheService();
  const cacheKey = CacheKeys.overview(
    shopId,
    startDate.toISOString(),
    endDate.toISOString(),
  );

  return await cache.getOrSet(
    cacheKey,
    async () => {
      // Calculate previous period dates (same duration as current period)
      const periodDuration = endDate.getTime() - startDate.getTime();
      const previousEndDate = new Date(startDate.getTime() - 1); // Day before current period starts
      const previousStartDate = new Date(
        previousEndDate.getTime() - periodDuration,
      );

      // Get current period metrics from unified analytics
      const [
        currentViewCount,
        currentClickCount,
        currentRevenueStats,
        currentCustomerCount,
      ] = await Promise.all([
        prisma.user_interactions.count({
          where: {
            shop_id: shopId,
            created_at: {
              gte: startDate,
              lte: endDate,
            },
            interaction_type: "view",
          },
        }),
        prisma.user_interactions.count({
          where: {
            shop_id: shopId,
            created_at: {
              gte: startDate,
              lte: endDate,
            },
            interaction_type: { in: ["click", "add_to_cart"] },
          },
        }),
        prisma.purchase_attributions.aggregate({
          where: {
            shop_id: shopId,
            purchase_at: {
              gte: startDate,
              lte: endDate,
            },
          },
          _sum: {
            total_revenue: true,
          },
          _avg: {
            total_revenue: true,
          },
        }),
        prisma.user_sessions
          .groupBy({
            by: ["customer_id"],
            where: {
              shop_id: shopId,
              created_at: {
                gte: startDate,
                lte: endDate,
              },
              customer_id: { not: null },
            },
          })
          .then((result) => result.length),
      ]);

      // Get previous period metrics from unified analytics
      const [
        previousViewCount,
        previousClickCount,
        previousRevenueStats,
        previousCustomerCount,
      ] = await Promise.all([
        prisma.user_interactions.count({
          where: {
            shop_id: shopId,
            created_at: {
              gte: previousStartDate,
              lte: previousEndDate,
            },
            interaction_type: "view",
          },
        }),
        prisma.user_interactions.count({
          where: {
            shop_id: shopId,
            created_at: {
              gte: previousStartDate,
              lte: previousEndDate,
            },
            interaction_type: { in: ["click", "add_to_cart"] },
          },
        }),
        prisma.purchase_attributions.aggregate({
          where: {
            shop_id: shopId,
            purchase_at: {
              gte: previousStartDate,
              lte: previousEndDate,
            },
          },
          _sum: {
            total_revenue: true,
          },
          _avg: {
            total_revenue: true,
          },
        }),
        prisma.user_sessions
          .groupBy({
            by: ["customer_id"],
            where: {
              shop_id: shopId,
              created_at: {
                gte: previousStartDate,
                lte: previousEndDate,
              },
              customer_id: { not: null },
            },
          })
          .then((result) => result.length),
      ]);

      // Calculate current period metrics
      const totalRecommendations = currentViewCount; // Use individual product views, not sessions
      const totalClicks = currentClickCount;
      const conversionRate =
        totalRecommendations > 0
          ? (totalClicks / totalRecommendations) * 100
          : 0;
      const totalRevenue = Number(currentRevenueStats._sum.total_revenue || 0);
      const averageOrderValue = Number(
        currentRevenueStats._avg.total_revenue || 0,
      );
      const totalCustomers = currentCustomerCount;

      // Calculate previous period metrics
      const previousConversionRate =
        previousViewCount > 0
          ? (previousClickCount / previousViewCount) * 100
          : 0;
      const previousTotalRevenue = Number(
        previousRevenueStats._sum.total_revenue || 0,
      );
      const previousAverageOrderValue = Number(
        previousRevenueStats._avg.total_revenue || 0,
      );
      const previousTotalCustomers = previousCustomerCount;

      // Calculate percentage changes
      const calculatePercentageChange = (
        current: number,
        previous: number,
      ): number | null => {
        if (previous === 0) {
          return null; // Return null for first period (no previous data to compare)
        }
        return Math.round(((current - previous) / previous) * 100 * 10) / 10; // Round to 1 decimal place
      };

      const revenueChange = calculatePercentageChange(
        totalRevenue,
        previousTotalRevenue,
      );
      const conversionRateChange = calculatePercentageChange(
        conversionRate,
        previousConversionRate,
      );
      const recommendationsChange = calculatePercentageChange(
        totalRecommendations,
        previousViewCount,
      );
      const clicksChange = calculatePercentageChange(
        totalClicks,
        previousClickCount,
      );
      const aovChange = calculatePercentageChange(
        averageOrderValue,
        previousAverageOrderValue,
      );
      const customersChange = calculatePercentageChange(
        totalCustomers,
        previousTotalCustomers,
      );

      return {
        total_revenue: totalRevenue,
        conversion_rate: Math.round(conversionRate * 100) / 100,
        total_recommendations: totalRecommendations,
        total_clicks: totalClicks,
        average_order_value: averageOrderValue,
        period: "last_30_days",
        currency_code: currencyCode,
        money_format: moneyFormat,
        // Period-over-period changes
        revenue_change: revenueChange,
        conversion_rate_change: conversionRateChange,
        recommendations_change: recommendationsChange,
        clicks_change: clicksChange,
        aov_change: aovChange,
        // NEW: Customer metrics
        total_customers: totalCustomers,
        customers_change: customersChange,
      };
    },
    CacheTTL.OVERVIEW,
  );
}

async function getTopProducts(
  shopId: string,
  startDate: Date,
  endDate: Date,
  limit: number = 10,
  currencyCode: string,
): Promise<TopProductData[]> {
  // Get all interactions for the period
  const allInteractions = await prisma.user_interactions.findMany({
    where: {
      shop_id: shopId,
      created_at: {
        gte: startDate,
        lte: endDate,
      },
      interaction_type: { in: ["click", "add_to_cart", "view"] },
    },
    select: {
      interaction_type: true,
      metadata: true,
    },
  });

  // Process interactions to extract product data
  const productStats = new Map<
    string,
    {
      clicks: number;
      views: number;
      customers: Set<string>;
    }
  >();

  allInteractions.forEach((interaction) => {
    const metadata = interaction.metadata as any;
    const productId = metadata?.product_id;
    // Only process interactions that have product data
    if (!productId || typeof productId !== "string") return;

    if (!productStats.has(productId)) {
      productStats.set(productId, {
        clicks: 0,
        views: 0,
        customers: new Set(),
      });
    }

    const stats = productStats.get(productId)!;

    if (interaction.interaction_type === "view") {
      stats.views++;
    } else if (["click", "add_to_cart"].includes(interaction.interactionType)) {
      stats.clicks++;
    }

    // Extract customer ID from metadata if available
    const customerId = metadata?.customerId;
    if (customerId) {
      stats.customers.add(customerId);
    }
  });

  // Sort by clicks and take top products
  const topProductClicks = Array.from(productStats.entries())
    .map(([productId, stats]) => ({
      productId,
      clicks: stats.clicks,
      views: stats.views,
      customers: stats.customers.size,
    }))
    .sort((a, b) => b.clicks - a.clicks)
    .slice(0, limit);

  if (topProductClicks.length === 0) {
    return [];
  }

  const topProductIds = topProductClicks
    .map((item) => item.productId)
    .filter(Boolean);

  // Get revenue data for the period
  const revenueData = await prisma.purchase_attributions.aggregate({
    where: {
      shop_id: shopId,
      purchase_at: {
        gte: startDate,
        lte: endDate,
      },
    },
    _sum: {
      total_revenue: true,
    },
  });

  const totalRevenue = Number(revenueData._sum.total_revenue || 0);

  // Combine data maintaining the order from topProductClicks
  const result = topProductClicks.map((item) => ({
    product_id: item.productId,
    clicks: item.clicks,
    recommendations_shown: item.views,
    customers: item.customers,
    revenue: totalRevenue / topProductClicks.length, // Distribute evenly for now
  }));

  // Get actual product titles from ProductData table
  const productTitles = await prisma.product_data.findMany({
    where: {
      shop_id: shopId,
      product_id: { in: topProductIds },
    },
    select: {
      product_id: true,
      title: true,
    },
  });

  const titleMap = new Map(
    productTitles.map((product) => [product.product_id, product.title]),
  );

  return result.map((row) => {
    const clicks = Number(row.clicks);
    const recommendationsShown = Number(row.recommendations_shown);
    const conversionRate =
      recommendationsShown > 0 ? (clicks / recommendationsShown) * 100 : 0;

    return {
      product_id: row.product_id,
      title: titleMap.get(row.product_id) || `Product ${row.product_id}`,
      revenue: row.revenue,
      clicks,
      conversion_rate: Math.round(conversionRate * 100) / 100,
      recommendations_shown: recommendationsShown,
      currency_code: currencyCode,
      customers: row.customers,
    };
  });
}

async function getRecentActivity(
  shopId: string,
  startDate: Date,
  endDate: Date,
  currencyCode: string,
): Promise<RecentActivityData> {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  // Calculate start of this week (Monday)
  const thisWeekStart = new Date(today);
  const dayOfWeek = today.getDay(); // 0 = Sunday, 1 = Monday, etc.
  const daysToMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // Adjust for Sunday being 0
  thisWeekStart.setDate(today.getDate() - daysToMonday);
  thisWeekStart.setHours(0, 0, 0, 0);

  // Optimized: Use conditional aggregation to get all periods in 3 queries
  const [recommendationsData, clicksData, revenueData, customersData] =
    await Promise.all([
      // Get recommendations for all periods in one query
      Promise.all([
        prisma.user_interactions.count({
          where: {
            shop_id: shopId,
            created_at: { gte: today, lte: endDate },
            interaction_type: "view",
          },
        }),
        prisma.user_interactions.count({
          where: {
            shop_id: shopId,
            created_at: { gte: yesterday, lt: today },
            interaction_type: "view",
          },
        }),
        prisma.user_interactions.count({
          where: {
            shop_id: shopId,
            created_at: { gte: thisWeekStart, lte: endDate },
            interaction_type: "view",
          },
        }),
      ]),
      // Get clicks for all periods in one query
      Promise.all([
        prisma.user_interactions.count({
          where: {
            shop_id: shopId,
            created_at: { gte: today, lte: endDate },
            interaction_type: { in: ["click", "add_to_cart"] },
          },
        }),
        prisma.user_interactions.count({
          where: {
            shop_id: shopId,
            created_at: { gte: yesterday, lt: today },
            interaction_type: { in: ["click", "add_to_cart"] },
          },
        }),
        prisma.user_interactions.count({
          where: {
            shop_id: shopId,
            created_at: { gte: thisWeekStart, lte: endDate },
            interaction_type: { in: ["click", "add_to_cart"] },
          },
        }),
      ]),
      // Get revenue for all periods in one query
      Promise.all([
        prisma.purchase_attributions.aggregate({
          where: {
            shop_id: shopId,
            purchase_at: { gte: today, lte: endDate },
          },
          _sum: { total_revenue: true },
        }),
        prisma.purchase_attributions.aggregate({
          where: {
            shop_id: shopId,
            purchase_at: { gte: yesterday, lt: today },
          },
          _sum: { total_revenue: true },
        }),
        prisma.purchase_attributions.aggregate({
          where: {
            shop_id: shopId,
            purchase_at: { gte: thisWeekStart, lte: endDate },
          },
          _sum: { total_revenue: true },
        }),
      ]),
      // Get customers for all periods in one query
      Promise.all([
        prisma.user_sessions
          .groupBy({
            by: ["customer_id"],
            where: {
              shop_id: shopId,
              created_at: { gte: today, lte: endDate },
              customer_id: { not: null },
            },
          })
          .then((result) => result.length),
        prisma.user_sessions
          .groupBy({
            by: ["customer_id"],
            where: {
              shop_id: shopId,
              created_at: { gte: yesterday, lt: today },
              customer_id: { not: null },
            },
          })
          .then((result) => result.length),
        prisma.user_sessions
          .groupBy({
            by: ["customer_id"],
            where: {
              shop_id: shopId,
              created_at: { gte: thisWeekStart, lte: endDate },
              customer_id: { not: null },
            },
          })
          .then((result) => result.length),
      ]),
    ]);

  return {
    today: {
      recommendations: recommendationsData[0],
      clicks: clicksData[0],
      revenue: Number(revenueData[0]._sum.total_revenue || 0),
      customers: customersData[0],
    },
    yesterday: {
      recommendations: recommendationsData[1],
      clicks: clicksData[1],
      revenue: Number(revenueData[1]._sum.total_revenue || 0),
      customers: customersData[1],
    },
    this_week: {
      recommendations: recommendationsData[2],
      clicks: clicksData[2],
      revenue: Number(revenueData[2]._sum.total_revenue || 0),
      customers: customersData[2],
    },
    currency_code: currencyCode,
  };
}

// Cache invalidation functions
export async function invalidateDashboardCache(
  shopDomain: string,
): Promise<void> {
  const cache = await getCacheService();
  const shopInfo = await getShopInfo(shopDomain);

  await Promise.all([
    cache.invalidateDashboard(shopInfo.id),
    cache.invalidateShop(shopDomain),
  ]);
}

export async function invalidateShopCache(shopDomain: string): Promise<void> {
  const cache = await getCacheService();
  await cache.invalidateShop(shopDomain);
}

async function getAttributedMetrics(
  shopId: string,
  startDate: Date,
  endDate: Date,
  currencyCode: string,
): Promise<AttributedMetrics> {
  const cache = await getCacheService();
  const cacheKey =
    CacheKeys.context(shopId, startDate.toISOString(), endDate.toISOString()) +
    ":attributed";

  return await cache.getOrSet(
    cacheKey,
    async () => {
      // Get attributed revenue from purchase attributions
      const attributedRevenueData =
        await prisma.purchase_attributions.aggregate({
          where: {
            shop_id: shopId,
            purchase_at: {
              gte: startDate,
              lte: endDate,
            },
          },
          _sum: {
            total_revenue: true,
          },
        });

      // Get total revenue for attribution rate calculation
      const totalRevenueData = await prisma.order_data.aggregate({
        where: {
          shop_id: shopId,
          order_date: {
            gte: startDate,
            lte: endDate,
          },
        },
        _sum: {
          total_amount: true,
        },
      });

      // Get attributed refunds from RefundAttributionAdjustment table
      // Using raw query since the Prisma client might not be updated
      const attributedRefundsResult = (await prisma.$queryRaw`
        SELECT COALESCE(SUM(total_refund_amount), 0) as total_refund_amount
        FROM refund_attribution_adjustments 
        WHERE shop_id = ${shopId} 
        AND computed_at >= ${startDate} 
        AND computed_at <= ${endDate}
      `) as Array<{ total_refund_amount: number }>;

      const attributedRefundsData = {
        _sum: {
          totalRefundAmount:
            attributedRefundsResult[0]?.total_refund_amount || 0,
        },
      };

      const attributedRevenue = Number(
        attributedRevenueData._sum.totalRevenue || 0,
      );
      const totalRevenue = Number(totalRevenueData._sum.totalAmount || 0);
      const attributedRefunds = Number(
        attributedRefundsData._sum.totalRefundAmount || 0,
      );

      const netAttributedRevenue = attributedRevenue - attributedRefunds;
      const attributionRate =
        totalRevenue > 0 ? (attributedRevenue / totalRevenue) * 100 : 0;
      const refundRate =
        attributedRevenue > 0
          ? (attributedRefunds / attributedRevenue) * 100
          : 0;

      return {
        attributed_revenue: attributedRevenue,
        attributed_refunds: attributedRefunds,
        net_attributed_revenue: netAttributedRevenue,
        attribution_rate: Math.round(attributionRate * 100) / 100,
        refund_rate: Math.round(refundRate * 100) / 100,
        currency_code: currencyCode,
      };
    },
    CacheTTL.CONTEXT,
  );
}

// Utility function to clear all caches (useful for testing)
export async function clearAllCaches(): Promise<void> {
  const cache = await getCacheService();
  await cache.delPattern("*");
}
