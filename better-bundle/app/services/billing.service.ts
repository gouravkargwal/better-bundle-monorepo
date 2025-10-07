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
