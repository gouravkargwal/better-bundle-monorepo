import prisma from "../db.server";
import { getCacheService, CacheKeys, CacheTTL } from "./redis.service";

// Constants
const DEFAULT_CURRENCY = "USD";
const DEFAULT_MONEY_FORMAT = "${{amount}}";
const DEFAULT_TOP_PRODUCTS_LIMIT = 10;
const PERCENTAGE_PRECISION = 100; // For rounding to 2 decimal places

// Enhanced interfaces with better type safety
export interface DashboardOverview {
  total_revenue: number;
  conversion_rate: number;
  total_recommendations: number;
  total_clicks: number;
  average_order_value: number;
  period: string;
  currency_code: string;
  money_format: string;
  revenue_change: number | null;
  conversion_rate_change: number | null;
  recommendations_change: number | null;
  clicks_change: number | null;
  aov_change: number | null;
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
  customers: number;
}

export interface RecentActivityData {
  today: ActivityMetrics;
  yesterday: ActivityMetrics;
  this_week: ActivityMetrics;
  currency_code: string;
}

export interface ActivityMetrics {
  recommendations: number;
  clicks: number;
  revenue: number;
  customers: number;
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

// Enhanced error types
class DashboardError extends Error {
  constructor(
    message: string,
    public code: string,
    public cause?: Error,
  ) {
    super(message);
    this.name = "DashboardError";
  }
}

// Utility functions
function safeNumber(value: unknown, defaultValue: number = 0): number {
  const num = Number(value);
  return isNaN(num) ? defaultValue : num;
}

function calculatePercentageChange(
  current: number,
  previous: number,
): number | null {
  if (previous === 0) return null;
  return Math.round(((current - previous) / previous) * 100 * 10) / 10;
}

function roundToDecimalPlaces(value: number, places: number = 2): number {
  const factor = Math.pow(10, places);
  return Math.round(value * factor) / factor;
}

function safeDivision(numerator: number, denominator: number): number {
  return denominator > 0 ? numerator / denominator : 0;
}

// Enhanced shop info retrieval with better error handling
async function getShopInfo(shopDomain: string): Promise<{
  id: string;
  currency_code: string;
  money_format: string;
}> {
  try {
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
          throw new DashboardError(
            `Shop not found: ${shopDomain}`,
            "SHOP_NOT_FOUND",
          );
        }

        return {
          id: shop.id,
          currency_code: shop.currency_code || DEFAULT_CURRENCY,
          money_format: shop.money_format || DEFAULT_MONEY_FORMAT,
        };
      },
      CacheTTL.SHOP,
    );
  } catch (error) {
    if (error instanceof DashboardError) throw error;
    throw new DashboardError(
      `Failed to retrieve shop info for ${shopDomain}`,
      "SHOP_INFO_ERROR",
      error as Error,
    );
  }
}

// Enhanced date utility with validation
function getDatesForPeriod(
  period: "last_30_days" | "last_7_days" | "today" = "last_30_days",
): { startDate: Date; endDate: Date } {
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

// Main dashboard function with enhanced error handling
export async function getDashboardOverview(
  shopDomain: string,
  period: "last_30_days" | "last_7_days" | "today" = "last_30_days",
): Promise<DashboardData> {
  try {
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
        const [overview, topProducts, recentActivity, attributedMetrics] =
          await Promise.allSettled([
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
              DEFAULT_TOP_PRODUCTS_LIMIT,
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

        // Handle partial failures gracefully
        const results = {
          overview:
            overview.status === "fulfilled"
              ? overview.value
              : getEmptyOverview(shopInfo, period),
          topProducts:
            topProducts.status === "fulfilled" ? topProducts.value : [],
          recentActivity:
            recentActivity.status === "fulfilled"
              ? recentActivity.value
              : getEmptyRecentActivity(shopInfo.currency_code),
          attributedMetrics:
            attributedMetrics.status === "fulfilled"
              ? attributedMetrics.value
              : getEmptyAttributedMetrics(shopInfo.currency_code),
        };

        // Log any failures
        [overview, topProducts, recentActivity, attributedMetrics].forEach(
          (result, index) => {
            if (result.status === "rejected") {
              const sections = [
                "overview",
                "topProducts",
                "recentActivity",
                "attributedMetrics",
              ];
              console.error(
                `Dashboard ${sections[index]} failed for shop ${shopDomain}:`,
                result.reason,
              );
            }
          },
        );

        return results;
      },
      CacheTTL.DASHBOARD,
    );
  } catch (error) {
    throw new DashboardError(
      `Failed to get dashboard overview for ${shopDomain}`,
      "DASHBOARD_ERROR",
      error as Error,
    );
  }
}

// Optimized overview metrics with better query structure
async function getOverviewMetrics(
  shopId: string,
  startDate: Date,
  endDate: Date,
  currencyCode: string,
  moneyFormat: string,
): Promise<DashboardOverview> {
  try {
    const cache = await getCacheService();
    const cacheKey = CacheKeys.overview(
      shopId,
      startDate.toISOString(),
      endDate.toISOString(),
    );

    return await cache.getOrSet(
      cacheKey,
      async () => {
        const periodDuration = endDate.getTime() - startDate.getTime();
        const previousEndDate = new Date(startDate.getTime() - 1);
        const previousStartDate = new Date(
          previousEndDate.getTime() - periodDuration,
        );

        // Optimized: Use fewer, more efficient queries
        const [currentMetrics, previousMetrics] = await Promise.all([
          getMetricsForPeriod(shopId, startDate, endDate),
          getMetricsForPeriod(shopId, previousStartDate, previousEndDate),
        ]);

        const conversionRate =
          safeDivision(currentMetrics.clicks, currentMetrics.views) * 100;
        const previousConversionRate =
          safeDivision(previousMetrics.clicks, previousMetrics.views) * 100;

        return {
          total_revenue: currentMetrics.revenue,
          conversion_rate: roundToDecimalPlaces(conversionRate),
          total_recommendations: currentMetrics.views,
          total_clicks: currentMetrics.clicks,
          average_order_value: currentMetrics.averageOrderValue,
          period: "last_30_days",
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
      },
      CacheTTL.OVERVIEW,
    );
  } catch (error) {
    throw new DashboardError(
      "Failed to get overview metrics",
      "OVERVIEW_ERROR",
      error as Error,
    );
  }
}

// Consolidated metrics query to reduce database calls
async function getMetricsForPeriod(
  shopId: string,
  startDate: Date,
  endDate: Date,
) {
  const [viewCount, clickCount, revenueStats, customerCount] =
    await Promise.all([
      prisma.user_interactions.count({
        where: {
          shop_id: shopId,
          created_at: { gte: startDate, lte: endDate },
          interaction_type: "view",
        },
      }),
      prisma.user_interactions.count({
        where: {
          shop_id: shopId,
          created_at: { gte: startDate, lte: endDate },
          interaction_type: { in: ["click", "add_to_cart"] },
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

  return {
    views: viewCount,
    clicks: clickCount,
    revenue: safeNumber(revenueStats._sum.total_revenue),
    averageOrderValue: safeNumber(revenueStats._avg.total_revenue),
    customers: customerCount,
  };
}

// Optimized top products with single query approach
async function getTopProducts(
  shopId: string,
  startDate: Date,
  endDate: Date,
  limit: number = DEFAULT_TOP_PRODUCTS_LIMIT,
  currencyCode: string,
): Promise<TopProductData[]> {
  try {
    // Get all interactions and process them in memory since we can't group by JSON
    const interactions = await prisma.user_interactions.findMany({
      where: {
        shop_id: shopId,
        created_at: { gte: startDate, lte: endDate },
        interaction_type: { in: ["click", "add_to_cart", "view"] },
      },
      select: {
        interaction_metadata: true,
        interaction_type: true,
        customer_id: true,
      },
    });

    // Process and aggregate data
    const productStats = new Map();

    for (const interaction of interactions) {
      const metadata = interaction.interaction_metadata as any;
      const productId = metadata?.product_id;

      if (!productId || typeof productId !== "string") continue;

      if (!productStats.has(productId)) {
        productStats.set(productId, {
          clicks: 0,
          views: 0,
          customers: new Set(),
        });
      }

      const stats = productStats.get(productId);
      if (interaction.interaction_type === "view") {
        stats.views++;
      } else if (
        interaction.interaction_type === "click" ||
        interaction.interaction_type === "add_to_cart"
      ) {
        stats.clicks++;
      }

      if (interaction.customer_id) {
        stats.customers.add(interaction.customer_id);
      }
    }

    // Get product titles in a single query
    const productIds = Array.from(productStats.keys());
    const productTitles = await prisma.productData.findMany({
      where: { shop_id: shopId, product_id: { in: productIds } },
      select: { product_id: true, title: true },
    });

    const titleMap = new Map(
      productTitles.map((product: any) => [product.product_id, product.title]),
    );

    // Calculate total revenue for distribution
    const revenueData = await prisma.purchase_attributions.aggregate({
      where: {
        shop_id: shopId,
        purchase_at: { gte: startDate, lte: endDate },
      },
      _sum: { total_revenue: true },
    });

    const totalRevenue = safeNumber(revenueData._sum.total_revenue);

    return Array.from(productStats.entries())
      .map(([productId, stats]) => ({
        product_id: productId,
        title: titleMap.get(productId) || `Product ${productId}`,
        revenue: totalRevenue / Math.max(productStats.size, 1),
        clicks: stats.clicks,
        conversion_rate: roundToDecimalPlaces(
          safeDivision(stats.clicks, stats.views) * 100,
        ),
        recommendations_shown: stats.views,
        currency_code: currencyCode,
        customers: stats.customers.size,
      }))
      .sort((a, b) => b.clicks - a.clicks)
      .slice(0, limit);
  } catch (error) {
    console.error("Error in getTopProducts:", error);
    return []; // Return empty array instead of throwing
  }
}

// Enhanced recent activity with better date handling
async function getRecentActivity(
  shopId: string,
  startDate: Date,
  endDate: Date,
  currencyCode: string,
): Promise<RecentActivityData> {
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
    throw new DashboardError(
      "Failed to get recent activity",
      "ACTIVITY_ERROR",
      error as Error,
    );
  }
}

function getActivityDateRanges() {
  const now = new Date();
  const todayStart = new Date(now);
  todayStart.setHours(0, 0, 0, 0);

  const yesterdayStart = new Date(todayStart);
  yesterdayStart.setDate(todayStart.getDate() - 1);

  const thisWeekStart = new Date(todayStart);
  const dayOfWeek = todayStart.getDay();
  const daysToMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
  thisWeekStart.setDate(todayStart.getDate() - daysToMonday);

  return { todayStart, yesterdayStart, thisWeekStart };
}

async function getActivityMetrics(
  shopId: string,
  startDate: Date,
  endDate: Date,
): Promise<ActivityMetrics> {
  const [recommendations, clicks, revenue, customers] = await Promise.all([
    prisma.user_interactions.count({
      where: {
        shop_id: shopId,
        created_at: { gte: startDate, lte: endDate },
        interaction_type: "view",
      },
    }),
    prisma.user_interactions.count({
      where: {
        shop_id: shopId,
        created_at: { gte: startDate, lte: endDate },
        interaction_type: { in: ["click", "add_to_cart"] },
      },
    }),
    prisma.purchase_attributions.aggregate({
      where: {
        shop_id: shopId,
        purchase_at: { gte: startDate, lte: endDate },
      },
      _sum: { total_revenue: true },
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
    recommendations,
    clicks,
    revenue: safeNumber(revenue._sum.total_revenue),
    customers,
  };
}

// Enhanced attributed metrics with prepared statement
async function getAttributedMetrics(
  shopId: string,
  startDate: Date,
  endDate: Date,
  currencyCode: string,
): Promise<AttributedMetrics> {
  try {
    const cache = await getCacheService();
    const cacheKey = `${CacheKeys.context(shopId, startDate.toISOString(), endDate.toISOString())}:attributed`;

    return await cache.getOrSet(
      cacheKey,
      async () => {
        const [attributedRevenueData, totalRevenueData, refundsResult] =
          await Promise.all([
            prisma.purchase_attributions.aggregate({
              where: {
                shop_id: shopId,
                purchase_at: { gte: startDate, lte: endDate },
              },
              _sum: { total_revenue: true },
            }),
            prisma.order_data.aggregate({
              where: {
                shop_id: shopId,
                order_date: { gte: startDate, lte: endDate },
              },
              _sum: { total_amount: true },
            }),
            prisma.refund_attributions.aggregate({
              where: {
                shop_id: shopId,
                refunded_at: { gte: startDate, lte: endDate },
              },
              _sum: { total_refund_amount: true },
            }),
          ]);

        const attributedRevenue = safeNumber(
          attributedRevenueData._sum?.total_revenue,
        );
        const totalRevenue = safeNumber(totalRevenueData._sum?.total_amount);
        const attributedRefunds = safeNumber(
          refundsResult._sum?.total_refund_amount,
        );

        const netAttributedRevenue = attributedRevenue - attributedRefunds;
        const attributionRate =
          safeDivision(attributedRevenue, totalRevenue) * 100;
        const refundRate =
          safeDivision(attributedRefunds, attributedRevenue) * 100;

        return {
          attributed_revenue: attributedRevenue,
          attributed_refunds: attributedRefunds,
          net_attributed_revenue: netAttributedRevenue,
          attribution_rate: roundToDecimalPlaces(attributionRate),
          refund_rate: roundToDecimalPlaces(refundRate),
          currency_code: currencyCode,
        };
      },
      CacheTTL.CONTEXT,
    );
  } catch (error) {
    throw new DashboardError(
      "Failed to get attributed metrics",
      "ATTRIBUTION_ERROR",
      error as Error,
    );
  }
}

// Fallback functions for graceful degradation
function getEmptyOverview(shopInfo: any, period: string): DashboardOverview {
  return {
    total_revenue: 0,
    conversion_rate: 0,
    total_recommendations: 0,
    total_clicks: 0,
    average_order_value: 0,
    period,
    currency_code: shopInfo.currency_code,
    money_format: shopInfo.money_format,
    revenue_change: null,
    conversion_rate_change: null,
    recommendations_change: null,
    clicks_change: null,
    aov_change: null,
    total_customers: 0,
    customers_change: null,
  };
}

function getEmptyRecentActivity(currencyCode: string): RecentActivityData {
  const emptyMetrics: ActivityMetrics = {
    recommendations: 0,
    clicks: 0,
    revenue: 0,
    customers: 0,
  };

  return {
    today: emptyMetrics,
    yesterday: emptyMetrics,
    this_week: emptyMetrics,
    currency_code: currencyCode,
  };
}

function getEmptyAttributedMetrics(currencyCode: string): AttributedMetrics {
  return {
    attributed_revenue: 0,
    attributed_refunds: 0,
    net_attributed_revenue: 0,
    attribution_rate: 0,
    refund_rate: 0,
    currency_code: currencyCode,
  };
}

// Enhanced cache invalidation with error handling
export async function invalidateDashboardCache(
  shopDomain: string,
): Promise<void> {
  try {
    const cache = await getCacheService();
    const shopInfo = await getShopInfo(shopDomain);

    await Promise.allSettled([
      cache.invalidateDashboard(shopInfo.id),
      cache.invalidateShop(shopDomain),
    ]);
  } catch (error) {
    console.error(
      `Failed to invalidate dashboard cache for ${shopDomain}:`,
      error,
    );
    // Don't throw - cache invalidation failure shouldn't break the app
  }
}

export async function invalidateShopCache(shopDomain: string): Promise<void> {
  try {
    const cache = await getCacheService();
    await cache.invalidateShop(shopDomain);
  } catch (error) {
    console.error(`Failed to invalidate shop cache for ${shopDomain}:`, error);
  }
}

export async function clearAllCaches(): Promise<void> {
  try {
    const cache = await getCacheService();
    await cache.delPattern("*");
  } catch (error) {
    console.error("Failed to clear all caches:", error);
    throw new DashboardError(
      "Failed to clear caches",
      "CACHE_CLEAR_ERROR",
      error as Error,
    );
  }
}
