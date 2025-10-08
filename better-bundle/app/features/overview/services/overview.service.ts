import prisma from "../../../db.server";

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

    return {
      shop,
      billingPlan,
      overviewData,
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
        pricing_tier_id: true,
        status: true,
        start_date: true,
        end_date: true,
        is_active: true,
        auto_renew: true,
        subscription_metadata: true,
        activated_at: true,
        suspended_at: true,
        cancelled_at: true,
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

    if (isTrialPhase) {
      // TRIAL PHASE: Show trial commission data (tracked but not charged)
      attributedRevenue = await prisma.commission_records.aggregate({
        where: {
          shop_id: shopId,
          billing_phase: "TRIAL",
          status: {
            in: ["TRIAL_PENDING", "TRIAL_COMPLETED"],
          },
        },
        _sum: {
          attributed_revenue: true,
        },
      });

      attributedOrders = await prisma.commission_records.count({
        where: {
          shop_id: shopId,
          billing_phase: "TRIAL",
          status: {
            in: ["TRIAL_PENDING", "TRIAL_COMPLETED"],
          },
        },
      });
    } else {
      // PAID PHASE: Show actual charged commission data
      attributedRevenue = await prisma.commission_records.aggregate({
        where: {
          shop_id: shopId,
          billing_phase: "PAID",
          status: {
            in: ["RECORDED", "INVOICED"],
          },
        },
        _sum: {
          commission_charged: true, // Use actual charged amount, not attributed revenue
        },
      });

      attributedOrders = await prisma.commission_records.count({
        where: {
          shop_id: shopId,
          billing_phase: "PAID",
          status: {
            in: ["RECORDED", "INVOICED"],
          },
        },
      });
    }

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
        pricing_tiers: {
          select: {
            commission_rate: true,
            trial_threshold_amount: true,
            currency: true,
          },
        },
      },
    });

    return {
      totalRevenue: isTrialPhase
        ? (attributedRevenue._sum as any).attributed_revenue || 0
        : (attributedRevenue._sum as any).commission_charged || 0,
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
            commissionRate: activePlan.pricing_tiers?.commission_rate || 0,
            thresholdAmount:
              activePlan.pricing_tiers?.trial_threshold_amount || 0,
            currency: activePlan.pricing_tiers?.currency || currencyCode,
            status: activePlan.status,
            startDate: activePlan.start_date,
            isActive: activePlan.is_active,
          }
        : null,
    };
  }
}
