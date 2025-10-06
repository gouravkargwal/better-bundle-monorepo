import prisma from "../db.server";
import { getCacheService } from "./redis.service";

// Constants
const DEFAULT_CURRENCY = "USD";
const DEFAULT_MONEY_FORMAT = "${{amount}}"; // eslint-disable-line no-template-curly-in-string
const DEFAULT_TOP_PRODUCTS_LIMIT = 10;

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

export interface PerformanceMetrics {
  total_recommendations: number;
  total_clicks: number;
  conversion_rate: number;
  total_customers: number;
  recommendations_change: number | null;
  clicks_change: number | null;
  conversion_rate_change: number | null;
  customers_change: number | null;
}

export interface DashboardData {
  overview: DashboardOverview;
  topProducts: TopProductData[];
  recentActivity: RecentActivityData;
  attributedMetrics: AttributedMetrics;
  performance: PerformanceMetrics;
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

// Enhanced shop info retrieval with better error handling - NO CACHE
async function getShopInfo(shopDomain: string): Promise<{
  id: string;
  currency_code: string;
  money_format: string;
}> {
  try {
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
  } catch (error) {
    if (error instanceof DashboardError) throw error;
    throw new DashboardError(
      `Failed to retrieve shop info for ${shopDomain}`,
      "SHOP_INFO_ERROR",
      error as Error,
    );
  }
}

// Enhanced date utility with validation - supports both presets and custom dates
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

/**
 * Main dashboard function with custom date range support
 * @param shopDomain - Shop domain
 * @param startDate - Start date (ISO string format YYYY-MM-DD) or preset ("last_30_days", "last_7_days", "today")
 * @param endDate - End date (ISO string format YYYY-MM-DD) - optional, required for custom ranges
 */
export async function getDashboardOverview(
  shopDomain: string,
  startDate: string = "last_30_days",
  endDate?: string,
): Promise<DashboardData> {
  try {
    const shopInfo = await getShopInfo(shopDomain);

    // Parse dates - support both custom ranges and presets
    let start: Date;
    let end: Date;
    let period: string;

    if (endDate) {
      // Custom date range - ensure UTC parsing
      start = new Date(startDate + "T00:00:00.000Z");
      end = new Date(endDate + "T23:59:59.999Z");
      period = "custom";

      // Validate date range
      if (isNaN(start.getTime()) || isNaN(end.getTime())) {
        throw new DashboardError(
          "Invalid date format. Use YYYY-MM-DD format",
          "INVALID_DATE_FORMAT",
        );
      }

      if (start > end) {
        throw new DashboardError(
          "Start date cannot be after end date",
          "INVALID_DATE_RANGE",
        );
      }

      // Limit to max 1 year of data for performance
      const maxDaysBack = 365;
      const daysDiff = Math.floor(
        (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24),
      );

      if (daysDiff > maxDaysBack) {
        throw new DashboardError(
          `Date range cannot exceed ${maxDaysBack} days`,
          "DATE_RANGE_TOO_LARGE",
        );
      }

      // Ensure end date is not in the future
      const now = new Date();
      if (end > now) {
        end = now;
      }
    } else {
      // Legacy preset support
      const dates = getDatesForPeriod(startDate as any);
      start = dates.startDate;
      end = dates.endDate;
      period = startDate;
    }

    const [
      overview,
      topProducts,
      recentActivity,
      attributedMetrics,
      performance,
    ] = await Promise.allSettled([
      getOverviewMetrics(
        shopInfo.id,
        start,
        end,
        shopInfo.currency_code,
        shopInfo.money_format,
        period,
      ),
      getTopProducts(
        shopInfo.id,
        start,
        end,
        DEFAULT_TOP_PRODUCTS_LIMIT,
        shopInfo.currency_code,
      ),
      getRecentActivity(shopInfo.id, start, end, shopInfo.currency_code),
      getAttributedMetrics(shopInfo.id, start, end, shopInfo.currency_code),
      getPerformanceMetrics(shopInfo.id, start, end),
    ]);

    // Handle partial failures gracefully
    const results = {
      overview:
        overview.status === "fulfilled"
          ? overview.value
          : getEmptyOverview(shopInfo, period),
      topProducts: topProducts.status === "fulfilled" ? topProducts.value : [],
      recentActivity:
        recentActivity.status === "fulfilled"
          ? recentActivity.value
          : getEmptyRecentActivity(shopInfo.currency_code),
      attributedMetrics:
        attributedMetrics.status === "fulfilled"
          ? attributedMetrics.value
          : getEmptyAttributedMetrics(shopInfo.currency_code),
      performance:
        performance.status === "fulfilled"
          ? performance.value
          : getEmptyPerformance(),
    };

    // Log any failures
    [
      overview,
      topProducts,
      recentActivity,
      attributedMetrics,
      performance,
    ].forEach((result, index) => {
      if (result.status === "rejected") {
        const sections = [
          "overview",
          "topProducts",
          "recentActivity",
          "attributedMetrics",
          "performance",
        ];
        console.error(
          `Dashboard ${sections[index]} failed for shop ${shopDomain}:`,
          result.reason,
        );
      }
    });

    return results;
  } catch (error) {
    if (error instanceof DashboardError) throw error;
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
  period: string,
): Promise<DashboardOverview> {
  try {
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
      period: period,
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
  } catch (error) {
    throw new DashboardError(
      "Failed to get overview metrics",
      "OVERVIEW_ERROR",
      error as Error,
    );
  }
}

// FIXED: Consolidated metrics query with correct interaction types
async function getMetricsForPeriod(
  shopId: string,
  startDate: Date,
  endDate: Date,
) {
  const [viewCount, clickCount, purchasesAgg, refundsAgg, customerCount] =
    await Promise.all([
      // Count views from recommendation_viewed and product_viewed events
      prisma.user_interactions.count({
        where: {
          shop_id: shopId,
          created_at: { gte: startDate, lte: endDate },
          interaction_type: {
            in: ["recommendation_viewed", "product_viewed", "page_viewed"],
          },
        },
      }),
      // Count clicks from recommendation_add_to_cart and product_added_to_cart events
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
      prisma.refund_attributions.aggregate({
        where: {
          shop_id: shopId,
          refunded_at: { gte: startDate, lte: endDate },
        },
        _sum: { total_refunded_revenue: true },
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
  const purchases = safeNumber(purchasesAgg._sum.total_revenue);
  const refunds = safeNumber(refundsAgg._sum.total_refunded_revenue);
  const netRevenue = Math.max(0, purchases - refunds);
  return {
    views: viewCount,
    clicks: clickCount,
    revenue: netRevenue,
    averageOrderValue: safeNumber(purchasesAgg._avg.total_revenue),
    customers: customerCount,
  };
}

// Performance metrics derived from core metrics with caching
async function getPerformanceMetrics(
  shopId: string,
  startDate: Date,
  endDate: Date,
): Promise<PerformanceMetrics> {
  try {
    const periodDuration = endDate.getTime() - startDate.getTime();
    const previousEndDate = new Date(startDate.getTime() - 1);
    const previousStartDate = new Date(
      previousEndDate.getTime() - periodDuration,
    );

    const [currentMetrics, previousMetrics] = await Promise.all([
      getMetricsForPeriod(shopId, startDate, endDate),
      getMetricsForPeriod(shopId, previousStartDate, previousEndDate),
    ]);

    const currentConversionRate =
      safeDivision(currentMetrics.clicks, currentMetrics.views) * 100;
    const previousConversionRate =
      safeDivision(previousMetrics.clicks, previousMetrics.views) * 100;

    return {
      total_recommendations: currentMetrics.views,
      total_clicks: currentMetrics.clicks,
      conversion_rate: roundToDecimalPlaces(currentConversionRate, 1),
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
  } catch (error) {
    throw new DashboardError(
      "Failed to get performance metrics",
      "PERFORMANCE_ERROR",
      error as Error,
    );
  }
}

// FIXED: Enhanced top products with correct interaction types and metadata extraction
async function getTopProducts(
  shopId: string,
  startDate: Date,
  endDate: Date,
  limit: number,
  currencyCode: string,
): Promise<TopProductData[]> {
  try {
    // Get product interactions with correct interaction types
    const interactions = await prisma.user_interactions.findMany({
      where: {
        shop_id: shopId,
        created_at: { gte: startDate, lte: endDate },
        interaction_type: {
          in: [
            "recommendation_viewed",
            "product_viewed",
            "recommendation_add_to_cart",
            "product_added_to_cart",
          ],
        },
      },
      select: {
        interaction_type: true,
        interaction_metadata: true,
        customer_id: true,
      },
    });

    // Aggregate product stats by extracting product_id from metadata
    const productStats = new Map<
      string,
      { views: number; clicks: number; customers: Set<string> }
    >();

    interactions.forEach((interaction) => {
      // Extract product ID from interaction metadata
      let productId: string | null = null;

      // Handle different metadata structures based on extension type
      const metadata = interaction.interaction_metadata as any;

      if (metadata?.data?.recommendations) {
        // Phoenix extension format
        productId = metadata.data.recommendations[0]?.id;
      } else if (metadata?.data?.productVariant?.product?.id) {
        // Atlas product_viewed format
        productId = metadata.data.productVariant.product.id;
      } else if (metadata?.data?.cartLine?.merchandise?.product?.id) {
        // Atlas product_added_to_cart format
        productId = metadata.data.cartLine.merchandise.product.id;
      }

      if (!productId) return;

      if (!productStats.has(productId)) {
        productStats.set(productId, {
          views: 0,
          clicks: 0,
          customers: new Set(),
        });
      }

      const stats = productStats.get(productId)!;

      if (
        interaction.interaction_type === "recommendation_viewed" ||
        interaction.interaction_type === "product_viewed"
      ) {
        stats.views++;
      } else if (
        interaction.interaction_type === "recommendation_add_to_cart" ||
        interaction.interaction_type === "product_added_to_cart"
      ) {
        stats.clicks++;
      }

      if (interaction.customer_id) {
        stats.customers.add(interaction.customer_id);
      }
    });

    // Get product titles
    const productIds = Array.from(productStats.keys());
    const products = await prisma.product_data.findMany({
      where: { product_id: { in: productIds }, shop_id: shopId },
      select: { product_id: true, title: true },
    });

    const titleMap = new Map(products.map((p) => [p.product_id, p.title]));

    // No reliable per-product attribution stored yet; hide revenue for now

    return Array.from(productStats.entries())
      .map(([productId, stats]) => ({
        product_id: productId,
        title: titleMap.get(productId) || `Product ${productId}`,
        revenue: 0,
        clicks: stats.clicks,
        conversion_rate: roundToDecimalPlaces(
          safeDivision(stats.clicks, stats.views) * 100,
        ),
        recommendations_shown: stats.views,
        currency_code: currencyCode,
        customers: stats.customers.size,
      }))
      .sort((a, b) =>
        a.conversion_rate !== b.conversion_rate
          ? b.conversion_rate - a.conversion_rate
          : b.clicks - a.clicks,
      )
      .slice(0, limit);
  } catch (error) {
    console.error("Error in getTopProducts:", error);
    return [];
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

// FIXED: Activity metrics with correct interaction types
async function getActivityMetrics(
  shopId: string,
  startDate: Date,
  endDate: Date,
): Promise<ActivityMetrics> {
  const [recommendations, clicks, purchasesAgg, refundsAgg, customers] =
    await Promise.all([
      // Count recommendations viewed (phoenix and atlas)
      prisma.user_interactions.count({
        where: {
          shop_id: shopId,
          created_at: { gte: startDate, lte: endDate },
          interaction_type: {
            in: ["recommendation_viewed", "product_viewed"],
          },
        },
      }),
      // Count clicks and add to cart events
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
      }),
      prisma.refund_attributions.aggregate({
        where: {
          shop_id: shopId,
          refunded_at: { gte: startDate, lte: endDate },
        },
        _sum: { total_refunded_revenue: true },
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

  const purchases = safeNumber(purchasesAgg._sum.total_revenue);
  const refunds = safeNumber(refundsAgg._sum.total_refunded_revenue);
  const netRevenue = Math.max(0, purchases - refunds);

  return {
    recommendations,
    clicks,
    revenue: netRevenue,
    customers,
  };
}

// FIXED: Enhanced attributed metrics - CORRECTLY using refund_attributions table
async function getAttributedMetrics(
  shopId: string,
  startDate: Date,
  endDate: Date,
  currencyCode: string,
): Promise<AttributedMetrics> {
  try {
    // DEBUG: Check if there's a cache issue - let's see what getShopInfo returns
    // We need to get the shop domain from somewhere - let's use the shop_id to find the domain
    const shopInfo = await prisma.shops.findUnique({
      where: { id: shopId },
      select: { id: true, shop_domain: true },
    });

    // Use the shop_id from the database query (should be the correct one)
    const correctShopId = shopInfo?.id || shopId;

    // Get attributed revenue from purchase_attributions table
    const attributedRevenueData = await prisma.purchase_attributions.aggregate({
      where: {
        shop_id: correctShopId, // Use the correct shop_id
        purchase_at: { gte: startDate, lte: endDate },
      },
      _sum: { total_revenue: true },
    });

    // FIXED: Get attributed refunds from refund_attributions table (NOT purchase_attributions)
    const attributedRefundsData = await prisma.refund_attributions.aggregate({
      where: {
        shop_id: correctShopId, // Use the correct shop_id
        refunded_at: { gte: startDate, lte: endDate },
      },
      _sum: {
        total_refund_amount: true,
        total_refunded_revenue: true,
      },
    });

    // Get total revenue for attribution rate from order_data table
    const totalRevenueData = await prisma.order_data.aggregate({
      where: {
        shop_id: correctShopId, // Use the correct shop_id
        order_date: { gte: startDate, lte: endDate },
      },
      _sum: { total_amount: true },
    });

    const attributedRevenue = safeNumber(
      attributedRevenueData._sum.total_revenue,
    );

    // Use total_refunded_revenue which is the attributed portion of refunds
    const attributedRefunds = safeNumber(
      attributedRefundsData._sum.total_refunded_revenue,
    );

    const totalRevenue = safeNumber(totalRevenueData._sum.total_amount);
    const netAttributedRevenue = attributedRevenue - attributedRefunds;

    const attributionRate = safeDivision(attributedRevenue, totalRevenue) * 100;
    const refundRate = safeDivision(attributedRefunds, attributedRevenue) * 100;

    return {
      attributed_revenue: attributedRevenue,
      attributed_refunds: attributedRefunds,
      net_attributed_revenue: netAttributedRevenue,
      attribution_rate: roundToDecimalPlaces(attributionRate),
      refund_rate: roundToDecimalPlaces(refundRate),
      currency_code: currencyCode,
    };
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

function getEmptyPerformance(): PerformanceMetrics {
  return {
    total_recommendations: 0,
    total_clicks: 0,
    conversion_rate: 0,
    total_customers: 0,
    recommendations_change: null,
    clicks_change: null,
    conversion_rate_change: null,
    customers_change: null,
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
