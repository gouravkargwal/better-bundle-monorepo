import prisma from "../db.server";

export interface TrialRevenueData {
  attributedRevenue: number;
  commissionEarned: number;
}
export async function getTrialRevenueData(
  shopId: string,
): Promise<TrialRevenueData> {
  try {
    const aggregate = await prisma.commission_records.aggregate({
      where: {
        shop_id: shopId,
        billing_phase: "TRIAL",
      },
      _sum: {
        attributed_revenue: true,
        commission_earned: true,
      },
    });

    const attributed_revenue = Number(aggregate?._sum?.attributed_revenue || 0);
    const commission_earned = Number(aggregate?._sum?.commission_earned || 0);

    return {
      attributedRevenue: attributed_revenue,
      commissionEarned: commission_earned,
    };
  } catch (error) {
    console.error(
      `Error getting trial revenue data for shop ${shopId}:`,
      error,
    );
    throw error;
  }
}

export async function getUsageRevenueData(
  shopId: string,
): Promise<TrialRevenueData> {
  try {
    const aggregate = await prisma.commission_records.aggregate({
      where: {
        shop_id: shopId,
        billing_phase: "PAID",
        status: "RECORDED",
      },
      _sum: {
        attributed_revenue: true,
        commission_earned: true,
      },
    });

    return {
      attributedRevenue: Number(aggregate._sum?.attributed_revenue || 0),
      commissionEarned: Number(aggregate._sum?.commission_earned || 0),
    };
  } catch (error) {
    console.error(
      `Error getting usage revenue data for shop ${shopId}:`,
      error,
    );
    throw error;
  }
}

export interface CurrentCycleMetrics {
  purchases: { count: number; total: number };
  net_revenue: number;
  commission: number;
  final_commission: number;
  capped_amount: number;
  days_remaining: number;
}

export async function getCurrentCycleMetrics(
  shopId: string,
  billingPlan: any,
): Promise<CurrentCycleMetrics> {
  try {
    // Get current billing cycle start date (from trial completion or subscription start)
    const cycleStart =
      billingPlan.trial_completed_at ||
      billingPlan.subscription_activated_at ||
      new Date();
    const cycleEnd = new Date(cycleStart);
    cycleEnd.setDate(cycleEnd.getDate() + 30); // 30-day cycle

    // Get commission records for current cycle (only PAID phase, not trial)
    const commissionRecords = await prisma.commission_records.findMany({
      where: {
        shop_id: shopId,
        billing_phase: "PAID", // Only post-trial commissions
        billing_cycle_start: {
          gte: cycleStart,
          lt: cycleEnd,
        },
      },
    });

    // Calculate metrics
    const purchases = commissionRecords.filter(
      (r) => r.status === "RECORDED" || r.status === "INVOICED",
    );

    const purchasesCount = purchases.length;
    const purchasesTotal = purchases.reduce(
      (sum, r) => sum + Number(r.attributed_revenue || 0),
      0,
    );

    const netRevenue = purchasesTotal;
    const commission = netRevenue * 0.03; // 3% commission
    const finalCommission = Math.min(
      commission,
      Number(billingPlan.configuration?.capped_amount || 1000),
    );

    // Calculate days remaining
    const now = new Date();
    const daysRemaining = Math.max(
      0,
      Math.ceil((cycleEnd.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)),
    );

    return {
      purchases: { count: purchasesCount, total: purchasesTotal },
      net_revenue: netRevenue,
      commission: commission,
      final_commission: finalCommission,
      capped_amount: Number(billingPlan.configuration?.capped_amount),
      days_remaining: daysRemaining,
    };
  } catch (error) {
    console.error("Error fetching current cycle metrics:", error);
    return {
      purchases: { count: 0, total: 0 },
      net_revenue: 0,
      commission: 0,
      final_commission: 0,
      capped_amount: Number(billingPlan.configuration?.capped_amount),
      days_remaining: 0,
    };
  }
}
