import prisma from "../../../db.server";
import logger from "../../../utils/logger";

export class OverviewService {
  async getOverviewData(shopDomain: string) {
    // Get shop info
    const shop = await this.getShopInfo(shopDomain);

    // Get billing plan
    const billingPlan = await this.getBillingPlan(shop.id);

    // Get simple overview metrics
    const overviewData = await this.getOverviewMetrics(
      shop.id,
      shop.currency_code || "USD",
    );

    // Get performance data
    const performanceData = await this.getPerformanceData(
      shop.id,
      shop.currency_code || "USD",
    );

    // Check TFRS readiness (is the recommendation engine ready?)
    const tfrsReadiness = await this.checkTfrsReadiness(shop.id);

    // Check setup progress
    const setupStatus = await this.getSetupStatus(
      shop.id,
      tfrsReadiness,
      shop.setup_guide_visited,
    );

    // Get recommendation analytics
    const recommendationAnalytics = await this.getRecommendationAnalytics(
      shop.id,
    );

    return {
      shop,
      billingPlan,
      overviewData,
      performanceData,
      setupStatus,
      recommendationAnalytics,
    };
  }

  private async getShopInfo(shopDomain: string) {
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: shopDomain },
      select: {
        id: true,
        shop_domain: true,
        currency_code: true,
        plan_type: true,
        created_at: true,
        setup_guide_visited: true,
      },
    });

    if (!shop) {
      throw new Error("Shop not found");
    }

    return shop;
  }

  private async getBillingPlan(shopId: string) {
    const billingPlan = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopId,
        status: "ACTIVE",
      },
      select: {
        id: true,
        subscription_plan_id: true,
        status: true,
        started_at: true,
        expires_at: true,
        is_active: true,
        auto_renew: true,
        shop_subscription_metadata: true,
      },
    });

    return billingPlan;
  }

  private async getOverviewMetrics(shopId: string, currencyCode: string) {
    // Revenue influenced by recommendations — sourced directly from
    // purchase_attributions (total_revenue is a summable Decimal; do not use
    // attributed_revenue, which is a JSON per-extension breakdown).
    const [attributedRevenue, attributedOrders, totalOrders, activePlan] =
      await Promise.all([
        prisma.purchase_attributions.aggregate({
          where: { shop_id: shopId },
          _sum: { total_revenue: true },
        }),
        prisma.purchase_attributions.count({ where: { shop_id: shopId } }),
        prisma.order_data.count({ where: { shop_id: shopId } }),
        prisma.shop_subscriptions.findFirst({
          where: { shop_id: shopId, is_active: true },
          include: {
            subscription_plans: {
              select: {
                name: true,
                plan_type: true,
                description: true,
                monthly_price: true,
              },
            },
          },
        }),
      ]);

    // Calculate conversion rate
    const conversionRate =
      totalOrders > 0 ? (attributedOrders / totalOrders) * 100 : 0;

    return {
      totalRevenue: Number(attributedRevenue._sum.total_revenue || 0),
      currency: currencyCode,
      conversionRate: Math.round(conversionRate * 100) / 100, // Round to 2 decimal places
      revenueChange: null, // TODO: Calculate period-over-period change
      conversionRateChange: null, // TODO: Calculate period-over-period change
      phaseLabel: "Revenue Influenced by Recommendations",
      // Additional data for future use
      totalOrders,
      attributedOrders,
      activePlan: activePlan
        ? {
            name: activePlan.subscription_plans?.name || "Unknown Plan",
            type: activePlan.subscription_plans?.plan_type || "UNKNOWN",
            description: activePlan.subscription_plans?.description,
            monthlyPrice: Number(
              activePlan.subscription_plans?.monthly_price || 0,
            ),
            currency: currencyCode,
            status: activePlan.status,
            startDate: activePlan.started_at,
            isActive: activePlan.is_active,
          }
        : null,
    };
  }

  private async getPerformanceData(shopId: string, currencyCode: string) {
    try {
      // Query purchase_attributions directly — it already has everything
      // needed (total_revenue, contributing_extensions), no join required.
      const attributions = await prisma.purchase_attributions.findMany({
        where: { shop_id: shopId },
        select: {
          id: true,
          total_revenue: true,
          order_id: true,
          created_at: true,
          contributing_extensions: true,
        },
        orderBy: {
          total_revenue: "desc",
        },
        take: 10,
      });

      // If no attributions, return empty data
      if (attributions.length === 0) {
        return {
          topBundles: [],
          revenueByExtension: [],
          trends: {
            weeklyGrowth: 0,
            monthlyGrowth: 0,
          },
        };
      }

      // Group by order_id to create "bundles" and get order details
      const orderStats = new Map();
      const orderIds = [...new Set(attributions.map((r) => r.order_id))];

      // Get order details for better naming
      const orderDetails = await prisma.order_data.findMany({
        where: {
          order_id: { in: orderIds },
          shop_id: shopId,
        },
        select: {
          order_id: true,
          order_name: true,
          total_amount: true,
        },
      });

      const orderDetailsMap = new Map();
      orderDetails.forEach((order) => {
        orderDetailsMap.set(order.order_id, order);
      });

      attributions.forEach((record) => {
        const orderId = record.order_id;
        if (!orderStats.has(orderId)) {
          const orderDetail = orderDetailsMap.get(orderId);
          const bundleName = orderDetail?.order_name
            ? `Bundle ${orderDetail.order_name}`
            : `Order ${orderId.slice(-6)}`;

          orderStats.set(orderId, {
            id: orderId,
            name: bundleName,
            revenue: 0,
            orders: 0,
            conversionRate: 0,
          });
        }
        const stats = orderStats.get(orderId);
        stats.revenue += Number(record.total_revenue) || 0;
        stats.orders += 1;
      });

      // Calculate total revenue for percentage calculation
      const totalRevenue = Array.from(orderStats.values()).reduce(
        (sum, bundle) => sum + bundle.revenue,
        0,
      );

      const topBundlesArray = Array.from(orderStats.values()).map((bundle) => ({
        ...bundle,
        conversionRate:
          totalRevenue > 0 ? (bundle.revenue / totalRevenue) * 100 : 0,
      }));

      // Get revenue by extension (where recommendations were shown)
      const extensionStats = new Map();

      attributions.forEach((record) => {
        if (record.contributing_extensions) {
          try {
            const extensions = record.contributing_extensions as any;
            if (Array.isArray(extensions)) {
              extensions.forEach((ext: any) => {
                const extensionName =
                  ext.extension_type ||
                  ext.extension_name ||
                  ext.name ||
                  "Unknown Extension";
                if (!extensionStats.has(extensionName)) {
                  extensionStats.set(extensionName, {
                    type: extensionName,
                    revenue: 0,
                    percentage: 0,
                  });
                }
                const stats = extensionStats.get(extensionName);
                stats.revenue += Number(record.total_revenue) || 0;
              });
            }
          } catch (error) {
            // Handle JSON parsing errors gracefully
            console.warn("Error parsing contributing_extensions:", error);
          }
        }
      });

      // Convert to array and calculate percentages
      const revenueByExtension = Array.from(extensionStats.values());
      if (totalRevenue > 0) {
        revenueByExtension.forEach((ext) => {
          ext.percentage = (ext.revenue / totalRevenue) * 100;
        });
      }

      // Sort by revenue descending
      revenueByExtension.sort((a, b) => b.revenue - a.revenue);

      // Calculate growth trends
      const currentMonth = new Date();
      const lastMonth = new Date(
        currentMonth.getFullYear(),
        currentMonth.getMonth() - 1,
        1,
      );

      const currentMonthRevenue = await prisma.purchase_attributions.aggregate({
        where: {
          shop_id: shopId,
          created_at: {
            gte: new Date(
              currentMonth.getFullYear(),
              currentMonth.getMonth(),
              1,
            ),
          },
        },
        _sum: {
          total_revenue: true,
        },
      });

      const lastMonthRevenue = await prisma.purchase_attributions.aggregate({
        where: {
          shop_id: shopId,
          created_at: {
            gte: lastMonth,
            lt: new Date(
              currentMonth.getFullYear(),
              currentMonth.getMonth(),
              1,
            ),
          },
        },
        _sum: {
          total_revenue: true,
        },
      });

      const currentRevenue =
        Number(currentMonthRevenue._sum.total_revenue) || 0;
      const previousRevenue = Number(lastMonthRevenue._sum.total_revenue) || 0;
      const monthlyGrowth =
        previousRevenue > 0
          ? ((currentRevenue - previousRevenue) / previousRevenue) * 100
          : 0;

      // Weekly growth (simplified calculation)
      const weeklyGrowth = monthlyGrowth / 4; // Rough approximation

      return {
        topBundles: topBundlesArray.slice(0, 3), // Top 3 bundles
        revenueByExtension,
        trends: {
          weeklyGrowth: Math.round(weeklyGrowth * 10) / 10,
          monthlyGrowth: Math.round(monthlyGrowth * 10) / 10,
        },
      };
    } catch (error) {
      console.error("Error fetching performance data:", error);
      // Return empty data structure on error
      return {
        topBundles: [],
        revenueByExtension: [],
        trends: {
          weeklyGrowth: 0,
          monthlyGrowth: 0,
        },
      };
    }
  }

  private async checkTfrsReadiness(shopId: string): Promise<{
    ready: boolean;
    productssynced: number;
    usersTracked: number;
    qualityScore: number;
  }> {
    try {
      const backendUrl = process.env.PYTHON_WORKER_API_URL;
      if (!backendUrl) {
        logger.warn(
          "PYTHON_WORKER_API_URL not set, skipping TFRS readiness check",
        );
        return {
          ready: false,
          productssynced: 0,
          usersTracked: 0,
          qualityScore: 0,
        } as any;
      }

      // Check TFRS readiness by looking at products in ProductData
      // (the canonical product table populated by data collection)
      const productCount = await prisma.product_data
        .count({
          where: { shop_id: shopId, is_active: true },
        })
        .catch(() => 0);

      // Use products as proxy for readiness — TFRS can train with just
      // product catalog (embeddings) for cold-start recommendations,
      // and user interactions are additive once orders arrive.
      const ready = productCount >= 3;
      logger.info(
        { productCount, ready },
        "TFRS readiness check result",
      );

      return {
        ready,
        productssynced: productCount,
        usersTracked: 0,
        qualityScore: ready ? 0.5 : 0,
      } as any;
    } catch (error: any) {
      logger.warn(
        { message: error?.message },
        "Could not check TFRS readiness",
      );
      return {
        ready: false,
        productssynced: 0,
        usersTracked: 0,
        qualityScore: 0,
      } as any;
    }
  }

  private async getSetupStatus(
    shopId: string,
    tfrsReadiness: {
      ready: boolean;
      productssynced: number;
      usersTracked: number;
      qualityScore: number;
    },
    setupGuideVisited: boolean,
  ) {
    try {
      const [productsCount, recommendationView] = await Promise.all([
        prisma.product_features.count({ where: { shop_id: shopId } }),
        prisma.user_interactions.findFirst({
          where: {
            shop_id: shopId,
            interaction_type: "recommendation_viewed",
          },
        }),
      ]);

      return {
        storeConnected: true,
        productsAnalyzed: productsCount > 0,
        productsCount,
        widgetAdded: false,
        recommendationsLive: !!recommendationView,
        recommendationsReady: tfrsReadiness.ready,
        qualityScore: tfrsReadiness.qualityScore,
        setupGuideVisited: setupGuideVisited,
        isSetupComplete: setupGuideVisited,
      };
    } catch (error) {
      console.error("Error checking setup status:", error);
      return {
        storeConnected: true,
        productsAnalyzed: false,
        productsCount: 0,
        widgetAdded: false,
        recommendationsLive: false,
        recommendationsReady: false,
        qualityScore: 0,
        setupGuideVisited: false,
        isSetupComplete: false,
      };
    }
  }

  private async getRecommendationAnalytics(shopId: string) {
    try {
      const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);

      const [revenueResult, clickResult, impressionResult] = await Promise.all([
        prisma.user_interactions.aggregate({
          _sum: { attributed_revenue: true },
          where: {
            shop_id: shopId,
            attributed_revenue: { gt: 0 },
            created_at: { gte: thirtyDaysAgo },
          },
        }),
        prisma.user_interactions.count({
          where: {
            shop_id: shopId,
            interaction_type: "recommendation_clicked",
            created_at: { gte: thirtyDaysAgo },
          },
        }),
        prisma.user_interactions.count({
          where: {
            shop_id: shopId,
            interaction_type: "recommendation_viewed",
            created_at: { gte: thirtyDaysAgo },
          },
        }),
      ]);

      return {
        totalRevenue: Number(revenueResult._sum.attributed_revenue || 0),
        totalClicks: clickResult,
        totalImpressions: impressionResult,
        ctr:
          impressionResult > 0
            ? Math.round((clickResult / impressionResult) * 10000) / 100
            : 0,
      };
    } catch (error) {
      logger.warn({ error }, "Failed to fetch recommendation analytics");
      return { totalRevenue: 0, totalClicks: 0, totalImpressions: 0, ctr: 0 };
    }
  }
}
