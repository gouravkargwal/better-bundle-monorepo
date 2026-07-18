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

    // Check Gorse readiness (is the recommendation engine ready?)
    const gorseReadiness = await this.checkGorseReadiness(shop.id);

    // Check setup progress
    const setupStatus = await this.getSetupStatus(
      shop.id,
      gorseReadiness,
      shop.setup_guide_visited,
    );

    return {
      shop,
      billingPlan,
      overviewData,
      performanceData,
      setupStatus,
    };
  }

  private async getShopInfo(shopDomain: string) {
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: shopDomain },
      select: {
        id: true,
        shop_domain: true,
        currency_code: true,
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
    // First, check if shop is in trial or paid phase
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopId,
        is_active: true,
      },
      select: {
        status: true,
        id: true,
      },
    });

    const isTrialPhase =
      shopSubscription?.status === "TRIAL" ||
      shopSubscription?.status === "TRIAL_COMPLETED";

    // Get attributed revenue based on phase
    let attributedRevenue;
    let attributedOrders;

    // Get total orders count for conversion rate calculation
    const totalOrders = await prisma.order_data.count({
      where: {
        shop_id: shopId,
      },
    });

    // Calculate conversion rate
    const conversionRate =
      totalOrders > 0 ? (attributedOrders / totalOrders) * 100 : 0;

    // Get active subscription plan details
    const activePlan = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopId,
        is_active: true,
      },
      include: {
        subscription_plans: {
          select: {
            name: true,
            plan_type: true,
            description: true,
          },
        },
      },
    });

    // ✅ Get commission charged separately for PAID phase
    let commissionCharged = 0;

    return {
      totalRevenue: (attributedRevenue._sum as any).attributed_revenue || 0,
      commissionCharged, // Actual commission charged to Shopify (PAID phase only)
      currency: currencyCode,
      conversionRate: Math.round(conversionRate * 100) / 100, // Round to 2 decimal places
      revenueChange: null, // TODO: Calculate period-over-period change
      conversionRateChange: null, // TODO: Calculate period-over-period change
      // Phase information
      isTrialPhase,
      phaseLabel: isTrialPhase ? "Trial Revenue" : "Total Revenue",
      phaseDescription: isTrialPhase
        ? shopSubscription?.status === "TRIAL_COMPLETED"
          ? "Trial completed - commission tracked (not charged yet)"
          : "Commission tracked during trial (not charged yet)"
        : "Commission charged to Shopify",
      // Additional data for future use
      totalOrders,
      attributedOrders,
      activePlan: activePlan
        ? {
            name: activePlan.subscription_plans?.name || "Unknown Plan",
            type: activePlan.subscription_plans?.plan_type || "UNKNOWN",
            description: activePlan.subscription_plans?.description,
            currency: "USD",
            status: activePlan.status,
            startDate: activePlan.started_at,
            isActive: activePlan.is_active,
          }
        : null,
    };
  }

  private async getPerformanceData(shopId: string, currencyCode: string) {
    try {
      // Group by order_id to create "bundles" and get order details
      const orderStats = new Map();

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

      // Convert to array and calculate percentages
      const revenueByExtension = Array.from(extensionStats.values());
      if (totalRevenue > 0) {
        revenueByExtension.forEach((ext) => {
          ext.percentage = (ext.revenue / totalRevenue) * 100;
        });
      }

      // Sort by revenue descending
      revenueByExtension.sort((a, b) => b.revenue - a.revenue);

      // Weekly growth (simplified calculation)

      return {
        topBundles: topBundlesArray.slice(0, 3), // Top 3 bundles
        revenueByExtension,
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

  private async checkGorseReadiness(shopId: string): Promise<{
    ready: boolean;
    productssynced: number;
    usersTracked: number;
    qualityScore: number;
  }> {
    try {
      const backendUrl = process.env.PYTHON_WORKER_API_URL;
      if (!backendUrl) {
        logger.warn(
          "PYTHON_WORKER_API_URL not set, skipping Gorse readiness check",
        );
        return {
          ready: false,
          productssynced: 0,
          usersTracked: 0,
          qualityScore: 0,
        } as any;
      }

      const response = await fetch(
        `${backendUrl}/api/v1/gorse/status/${shopId}`,
        {
          signal: AbortSignal.timeout(5000),
        },
      );

      if (!response.ok) {
        logger.warn({ status: response.status }, "Gorse status check failed");
        return {
          ready: false,
          productssynced: 0,
          usersTracked: 0,
          qualityScore: 0,
        } as any;
      }

      const data = await response.json();
      const featureCounts = data?.feature_utilization?.feature_counts || {};
      const productssynced = featureCounts.product_features || 0;
      const usersTracked = featureCounts.user_features || 0;
      const qualityScore = data?.quality_indicators?.overall_quality || 0;
      const gorseHealthy = data?.gorse_health?.success === true;

      const ready = gorseHealthy && productssynced > 0;
      logger.info(
        { gorseHealthy, productssynced, usersTracked, qualityScore, ready },
        "Gorse readiness check result",
      );

      return { ready, productssynced, usersTracked, qualityScore } as any;
    } catch (error: any) {
      logger.warn(
        { message: error?.message },
        "Could not reach Gorse for readiness check",
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
    gorseReadiness: {
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
        recommendationsReady: gorseReadiness.ready,
        qualityScore: gorseReadiness.qualityScore,
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
}
