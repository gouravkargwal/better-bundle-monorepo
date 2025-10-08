// features/overview/services/overview.service.ts
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
    // Get attributed revenue from commission records
    const attributedRevenue = await prisma.commission_records.aggregate({
      where: {
        shop_id: shopId,
        status: "RECORDED",
      },
      _sum: {
        attributed_revenue: true,
      },
    });

    // Get total orders count for conversion rate calculation
    const totalOrders = await prisma.order_data.count({
      where: {
        shop_id: shopId,
      },
    });

    // Get attributed orders count
    const attributedOrders = await prisma.commission_records.count({
      where: {
        shop_id: shopId,
        status: "RECORDED",
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
      totalRevenue: attributedRevenue._sum.attributed_revenue || 0,
      currency: currencyCode,
      conversionRate: Math.round(conversionRate * 100) / 100, // Round to 2 decimal places
      revenueChange: null, // TODO: Calculate period-over-period change
      conversionRateChange: null, // TODO: Calculate period-over-period change
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
