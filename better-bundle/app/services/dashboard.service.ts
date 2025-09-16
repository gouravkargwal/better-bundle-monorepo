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

export interface ContextPerformanceData {
  context: string;
  extension_type: string;
  revenue: number;
  conversion_rate: number;
  clicks: number;
  recommendations_shown: number;
  currency_code: string;
  // SIMPLIFIED: Only show actionable metrics
  customers: number;
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

// SIMPLIFIED: Extension Performance - what store owners care about
export interface ExtensionPerformanceData {
  extension_type: string;
  revenue: number;
  conversion_rate: number;
  customers: number;
  currency_code: string;
}

export interface DashboardData {
  overview: DashboardOverview;
  contextPerformance: ContextPerformanceData[];
  topProducts: TopProductData[];
  recentActivity: RecentActivityData;
  // SIMPLIFIED: Only extension performance (actionable for store owners)
  extensionPerformance: ExtensionPerformanceData[];
}

async function getShopInfo(shopDomain: string): Promise<{
  id: string;
  currencyCode: string;
  moneyFormat: string;
}> {
  const cache = await getCacheService();
  const cacheKey = CacheKeys.shop(shopDomain);

  return await cache.getOrSet(
    cacheKey,
    async () => {
      const shop = await prisma.shop.findUnique({
        where: { shopDomain },
        select: {
          id: true,
          currencyCode: true,
          moneyFormat: true,
        },
      });

      if (!shop) {
        throw new Error(`Shop not found: ${shopDomain}`);
      }

      return {
        id: shop.id,
        currencyCode: shop.currencyCode || "USD",
        moneyFormat: shop.moneyFormat || "${{amount}}",
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
      const [
        overview,
        contextPerformance,
        topProducts,
        recentActivity,
        extensionPerformance,
      ] = await Promise.all([
        getOverviewMetrics(
          shopInfo.id,
          startDate,
          endDate,
          shopInfo.currencyCode,
          shopInfo.moneyFormat,
        ),
        getContextPerformance(
          shopInfo.id,
          startDate,
          endDate,
          shopInfo.currencyCode,
        ),
        getTopProducts(
          shopInfo.id,
          startDate,
          endDate,
          10,
          shopInfo.currencyCode,
        ),
        getRecentActivity(
          shopInfo.id,
          startDate,
          endDate,
          shopInfo.currencyCode,
        ),
        getExtensionPerformance(
          shopInfo.id,
          startDate,
          endDate,
          shopInfo.currencyCode,
        ),
      ]);

      return {
        overview,
        contextPerformance,
        topProducts,
        recentActivity,
        extensionPerformance,
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
        prisma.userInteraction.count({
          where: {
            shopId,
            createdAt: {
              gte: startDate,
              lte: endDate,
            },
            interactionType: "view",
          },
        }),
        prisma.userInteraction.count({
          where: {
            shopId,
            createdAt: {
              gte: startDate,
              lte: endDate,
            },
            interactionType: { in: ["click", "add_to_cart"] },
          },
        }),
        prisma.purchaseAttribution.aggregate({
          where: {
            shopId,
            purchaseAt: {
              gte: startDate,
              lte: endDate,
            },
          },
          _sum: {
            totalRevenue: true,
          },
          _avg: {
            totalRevenue: true,
          },
        }),
        prisma.userSession.count({
          where: {
            shopId,
            createdAt: {
              gte: startDate,
              lte: endDate,
            },
            customerId: { not: null },
          },
          distinct: ["customerId"],
        }),
      ]);

      // Get previous period metrics from unified analytics
      const [
        previousViewCount,
        previousClickCount,
        previousRevenueStats,
        previousCustomerCount,
      ] = await Promise.all([
        prisma.userInteraction.count({
          where: {
            shopId,
            createdAt: {
              gte: previousStartDate,
              lte: previousEndDate,
            },
            interactionType: "view",
          },
        }),
        prisma.userInteraction.count({
          where: {
            shopId,
            createdAt: {
              gte: previousStartDate,
              lte: previousEndDate,
            },
            interactionType: { in: ["click", "add_to_cart"] },
          },
        }),
        prisma.purchaseAttribution.aggregate({
          where: {
            shopId,
            purchaseAt: {
              gte: previousStartDate,
              lte: previousEndDate,
            },
          },
          _sum: {
            totalRevenue: true,
          },
          _avg: {
            totalRevenue: true,
          },
        }),
        prisma.userSession.count({
          where: {
            shopId,
            createdAt: {
              gte: previousStartDate,
              lte: previousEndDate,
            },
            customerId: { not: null },
          },
          distinct: ["customerId"],
        }),
      ]);

      // Calculate current period metrics
      const totalRecommendations = currentViewCount; // Use individual product views, not sessions
      const totalClicks = currentClickCount;
      const conversionRate =
        totalRecommendations > 0
          ? (totalClicks / totalRecommendations) * 100
          : 0;
      const totalRevenue = Number(currentRevenueStats._sum.totalRevenue || 0);
      const averageOrderValue = Number(
        currentRevenueStats._avg.totalRevenue || 0,
      );
      const totalCustomers = currentCustomerCount;

      // Calculate previous period metrics
      const previousConversionRate =
        previousViewCount > 0
          ? (previousClickCount / previousViewCount) * 100
          : 0;
      const previousTotalRevenue = Number(
        previousRevenueStats._sum.totalRevenue || 0,
      );
      const previousAverageOrderValue = Number(
        previousRevenueStats._avg.totalRevenue || 0,
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

async function getContextPerformance(
  shopId: string,
  startDate: Date,
  endDate: Date,
  currencyCode: string,
): Promise<ContextPerformanceData[]> {
  const cache = await getCacheService();
  const cacheKey = CacheKeys.context(
    shopId,
    startDate.toISOString(),
    endDate.toISOString(),
  );

  return await cache.getOrSet(
    cacheKey,
    async () => {
      const contexts = ["profile", "order_status", "order_history"];

      // Get data from unified analytics tables
      const [
        recommendationsByContext,
        clicksByContext,
        revenueByContext,
        customersByContext,
      ] = await Promise.all([
        prisma.userInteraction.groupBy({
          by: ["context"],
          where: {
            shopId,
            createdAt: { gte: startDate, lte: endDate },
            interactionType: "view",
            context: { in: contexts },
          },
          _count: { _all: true },
        }),
        prisma.userInteraction.groupBy({
          by: ["context"],
          where: {
            shopId,
            createdAt: { gte: startDate, lte: endDate },
            interactionType: { in: ["click", "add_to_cart"] },
            context: { in: contexts },
          },
          _count: { _all: true },
        }),
        prisma.purchaseAttribution.groupBy({
          by: ["orderId"],
          where: {
            shopId,
            purchaseAt: { gte: startDate, lte: endDate },
          },
          _sum: { totalRevenue: true },
        }),
        prisma.userInteraction.groupBy({
          by: ["context"],
          where: {
            shopId,
            createdAt: { gte: startDate, lte: endDate },
            context: { in: contexts },
            customerId: { not: null },
          },
          _count: { customerId: true },
          distinct: ["customerId"],
        }),
      ]);

      // Create maps for efficient lookup
      const recommendationsMap = new Map(
        recommendationsByContext.map((item) => [
          item.context,
          item._count._all,
        ]),
      );
      const clicksMap = new Map(
        clicksByContext.map((item) => [item.context, item._count._all]),
      );
      const customersMap = new Map(
        customersByContext.map((item) => [
          item.context,
          item._count.customerId,
        ]),
      );

      // Calculate total revenue (simplified - we'll get this from purchase attributions)
      const totalRevenue = Number(
        revenueByContext.reduce(
          (sum, item) => sum + Number(item._sum.totalRevenue || 0),
          0,
        ),
      );

      // Merge data for all contexts
      return contexts.map((context) => {
        const recommendationsShown = recommendationsMap.get(context) || 0;
        const clicks = clicksMap.get(context) || 0;
        const customers = customersMap.get(context) || 0;
        const conversionRate =
          recommendationsShown > 0 ? (clicks / recommendationsShown) * 100 : 0;

        return {
          context,
          extension_type: "venus", // Default to venus for customer account contexts
          revenue: totalRevenue / contexts.length, // Distribute revenue evenly for now
          conversion_rate: Math.round(conversionRate * 100) / 100,
          clicks,
          recommendations_shown: recommendationsShown,
          currency_code: currencyCode,
          customers,
        };
      });
    },
    CacheTTL.CONTEXT,
  );
}

async function getExtensionPerformance(
  shopId: string,
  startDate: Date,
  endDate: Date,
  currencyCode: string,
): Promise<ExtensionPerformanceData[]> {
  const cache = await getCacheService();
  const cacheKey = CacheKeys.context(
    shopId,
    startDate.toISOString(),
    endDate.toISOString(),
  );

  return await cache.getOrSet(
    cacheKey,
    async () => {
      const extensionTypes = ["venus", "phoenix", "apollo", "atlas"];

      // Get extension performance data
      const [
        interactionsByExtension,
        revenueByExtension,
        customersByExtension,
      ] = await Promise.all([
        prisma.userInteraction.groupBy({
          by: ["extensionType"],
          where: {
            shopId,
            createdAt: { gte: startDate, lte: endDate },
            extensionType: { in: extensionTypes },
          },
          _count: { _all: true },
        }),
        prisma.purchaseAttribution.groupBy({
          by: ["orderId"],
          where: {
            shopId,
            purchaseAt: { gte: startDate, lte: endDate },
          },
          _sum: { totalRevenue: true },
        }),
        prisma.userInteraction.groupBy({
          by: ["extensionType"],
          where: {
            shopId,
            createdAt: { gte: startDate, lte: endDate },
            extensionType: { in: extensionTypes },
            customerId: { not: null },
          },
          _count: { customerId: true },
          distinct: ["customerId"],
        }),
      ]);

      // Create maps for efficient lookup
      const interactionsMap = new Map(
        interactionsByExtension.map((item) => [
          item.extensionType,
          item._count._all,
        ]),
      );
      const customersMap = new Map(
        customersByExtension.map((item) => [
          item.extensionType,
          item._count.customerId,
        ]),
      );

      // Calculate total revenue
      const totalRevenue = Number(
        revenueByExtension.reduce(
          (sum, item) => sum + Number(item._sum.totalRevenue || 0),
          0,
        ),
      );

      // Return extension performance data
      return extensionTypes.map((extensionType) => {
        const interactions = interactionsMap.get(extensionType) || 0;
        const customers = customersMap.get(extensionType) || 0;
        const revenue = totalRevenue / extensionTypes.length; // Distribute evenly for now
        const conversionRate =
          interactions > 0 ? (customers / interactions) * 100 : 0;

        return {
          extension_type: extensionType,
          revenue,
          conversion_rate: Math.round(conversionRate * 100) / 100,
          customers,
          currency_code: currencyCode,
        };
      });
    },
    CacheTTL.CONTEXT,
  );
}

async function getTopProducts(
  shopId: string,
  startDate: Date,
  endDate: Date,
  limit: number = 10,
  currencyCode: string,
): Promise<TopProductData[]> {
  // Optimized: Get top products by clicks first, then fetch related data
  const topProductClicks = await prisma.recommendationInteraction.groupBy({
    by: ["productId"],
    where: {
      session: {
        shopId,
        createdAt: {
          gte: startDate,
          lte: endDate,
        },
      },
      interactionType: { in: ["click", "add_to_cart"] },
    },
    _count: true,
    orderBy: {
      _count: {
        productId: "desc",
      },
    },
    take: limit,
  });

  if (topProductClicks.length === 0) {
    return [];
  }

  const topProductIds = topProductClicks.map((item) => item.productId);

  // Fetch views and revenue data only for top products
  const [productViews, productRevenue] = await Promise.all([
    prisma.recommendationInteraction.groupBy({
      by: ["productId"],
      where: {
        session: {
          shopId,
          createdAt: {
            gte: startDate,
            lte: endDate,
          },
        },
        interactionType: "view",
        productId: { in: topProductIds },
      },
      _count: true,
    }),
    prisma.recommendationAttribution.groupBy({
      by: ["productId"],
      where: {
        shopId,
        attributionDate: {
          gte: startDate,
          lte: endDate,
        },
        status: "confirmed",
        productId: { in: topProductIds },
      },
      _sum: {
        revenue: true,
      },
    }),
  ]);

  // Create maps for efficient lookup
  const viewsMap = new Map(
    productViews.map((item) => [item.productId, item._count]),
  );
  const revenueMap = new Map(
    productRevenue.map((item) => [item.productId, item._sum.revenue || 0]),
  );

  // Combine data maintaining the order from topProductClicks
  const result = topProductClicks.map((item) => ({
    product_id: item.productId,
    clicks: item._count,
    recommendations_shown: viewsMap.get(item.productId) || 0,
    revenue: revenueMap.get(item.productId) || 0,
  }));

  return result.map((row) => {
    const clicks = Number(row.clicks);
    const recommendationsShown = Number(row.recommendations_shown);
    const conversionRate =
      recommendationsShown > 0 ? (clicks / recommendationsShown) * 100 : 0;

    return {
      product_id: row.product_id,
      title: `Product ${row.product_id}`, // TODO: Get actual product title from Shopify
      revenue: row.revenue,
      clicks,
      conversion_rate: Math.round(conversionRate * 100) / 100,
      recommendations_shown: recommendationsShown,
      currency_code: currencyCode,
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
  const [recommendationsData, clicksData, revenueData] = await Promise.all([
    // Get recommendations for all periods in one query
    Promise.all([
      prisma.recommendationInteraction.count({
        where: {
          session: {
            shopId,
            createdAt: { gte: today, lte: endDate },
          },
          interactionType: "view",
        },
      }),
      prisma.recommendationInteraction.count({
        where: {
          session: {
            shopId,
            createdAt: { gte: yesterday, lt: today },
          },
          interactionType: "view",
        },
      }),
      prisma.recommendationInteraction.count({
        where: {
          session: {
            shopId,
            createdAt: { gte: thisWeekStart, lte: endDate },
          },
          interactionType: "view",
        },
      }),
    ]),
    // Get clicks for all periods in one query
    Promise.all([
      prisma.recommendationInteraction.count({
        where: {
          session: {
            shopId,
            createdAt: { gte: today, lte: endDate },
          },
          interactionType: { in: ["click", "add_to_cart"] },
        },
      }),
      prisma.recommendationInteraction.count({
        where: {
          session: {
            shopId,
            createdAt: { gte: yesterday, lt: today },
          },
          interactionType: { in: ["click", "add_to_cart"] },
        },
      }),
      prisma.recommendationInteraction.count({
        where: {
          session: {
            shopId,
            createdAt: { gte: thisWeekStart, lte: endDate },
          },
          interactionType: { in: ["click", "add_to_cart"] },
        },
      }),
    ]),
    // Get revenue for all periods in one query
    Promise.all([
      prisma.recommendationAttribution.aggregate({
        where: {
          shopId,
          attributionDate: { gte: today, lte: endDate },
          status: "confirmed",
        },
        _sum: { revenue: true },
      }),
      prisma.recommendationAttribution.aggregate({
        where: {
          shopId,
          attributionDate: { gte: yesterday, lt: today },
          status: "confirmed",
        },
        _sum: { revenue: true },
      }),
      prisma.recommendationAttribution.aggregate({
        where: {
          shopId,
          attributionDate: { gte: thisWeekStart, lte: endDate },
          status: "confirmed",
        },
        _sum: { revenue: true },
      }),
    ]),
  ]);

  return {
    today: {
      recommendations: recommendationsData[0],
      clicks: clicksData[0],
      revenue: revenueData[0]._sum.revenue || 0,
    },
    yesterday: {
      recommendations: recommendationsData[1],
      clicks: clicksData[1],
      revenue: revenueData[1]._sum.revenue || 0,
    },
    this_week: {
      recommendations: recommendationsData[2],
      clicks: clicksData[2],
      revenue: revenueData[2]._sum.revenue || 0,
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

// Utility function to clear all caches (useful for testing)
export async function clearAllCaches(): Promise<void> {
  const cache = await getCacheService();
  await cache.delPattern("*");
}
