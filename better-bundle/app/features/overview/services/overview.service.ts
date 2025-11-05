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

    // Get performance data
    const performanceData = await this.getPerformanceData(
      shop.id,
      shop.currency_code || "USD",
    );

    return {
      shop,
      billingPlan,
      overviewData,
      performanceData,
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
      // PAID PHASE: Get both attributed revenue AND commission charged separately
      const paidCommissionsData = await prisma.commission_records.aggregate({
        where: {
          shop_id: shopId,
          billing_phase: "PAID",
          status: {
            in: ["RECORDED", "INVOICED"],
          },
        },
        _sum: {
          attributed_revenue: true, // Actual revenue generated
          commission_charged: true, // Actual commission charged to Shopify
        },
      });

      attributedRevenue = {
        _sum: {
          attributed_revenue: paidCommissionsData._sum.attributed_revenue,
        },
      } as any;

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

    // ✅ Get commission charged separately for PAID phase
    let commissionCharged = 0;
    if (!isTrialPhase) {
      const paidCommissions = await prisma.commission_records.aggregate({
        where: {
          shop_id: shopId,
          billing_phase: "PAID",
          status: {
            in: ["RECORDED", "INVOICED"],
          },
        },
        _sum: {
          commission_charged: true,
        },
      });
      commissionCharged = Number(paidCommissions._sum.commission_charged || 0);
    }

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
            commissionRate: activePlan.pricing_tiers?.commission_rate || 0,
            thresholdAmount:
              activePlan.pricing_tiers?.trial_threshold_amount || 0,
            currency: activePlan.pricing_tiers?.currency || currencyCode,
            status: activePlan.status,
            startDate: activePlan.started_at,
            isActive: activePlan.is_active,
          }
        : null,
    };
  }

  private async getPerformanceData(shopId: string, currencyCode: string) {
    try {
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

      // Filter commission records based on phase
      const statusFilter = isTrialPhase
        ? ["TRIAL_PENDING", "TRIAL_COMPLETED"]
        : ["RECORDED", "INVOICED"];

      // Get commission records with purchase attribution data
      const commissionRecords = await prisma.commission_records.findMany({
        where: {
          shop_id: shopId,
          status: {
            in: statusFilter,
          },
        },
        select: {
          id: true,
          attributed_revenue: true,
          order_id: true,
          created_at: true,
          commission_metadata: true,
          purchase_attributions: {
            select: {
              contributing_extensions: true,
              metadata: true,
            },
          },
        },
        orderBy: {
          attributed_revenue: "desc",
        },
        take: 10,
      });

      // If no commission records, return empty data
      if (commissionRecords.length === 0) {
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
      const orderIds = [...new Set(commissionRecords.map((r) => r.order_id))];

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

      commissionRecords.forEach((record) => {
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
        stats.revenue += Number(record.attributed_revenue) || 0;
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

      commissionRecords.forEach((record) => {
        if (record.purchase_attributions?.contributing_extensions) {
          try {
            const extensions = record.purchase_attributions
              .contributing_extensions as any;
            if (Array.isArray(extensions)) {
              extensions.forEach((ext: any) => {
                const extensionName =
                  ext.extension_name || ext.name || "Unknown Extension";
                if (!extensionStats.has(extensionName)) {
                  extensionStats.set(extensionName, {
                    type: extensionName,
                    revenue: 0,
                    percentage: 0,
                  });
                }
                const stats = extensionStats.get(extensionName);
                stats.revenue += Number(record.attributed_revenue) || 0;
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

      const currentMonthRevenue = await prisma.commission_records.aggregate({
        where: {
          shop_id: shopId,
          created_at: {
            gte: new Date(
              currentMonth.getFullYear(),
              currentMonth.getMonth(),
              1,
            ),
          },
          status: {
            in: statusFilter,
          },
        },
        _sum: {
          attributed_revenue: true,
        },
      });

      const lastMonthRevenue = await prisma.commission_records.aggregate({
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
          status: {
            in: statusFilter,
          },
        },
        _sum: {
          attributed_revenue: true,
        },
      });

      const currentRevenue =
        Number(currentMonthRevenue._sum.attributed_revenue) || 0;
      const previousRevenue =
        Number(lastMonthRevenue._sum.attributed_revenue) || 0;
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
}
