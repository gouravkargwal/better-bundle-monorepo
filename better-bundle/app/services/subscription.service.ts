import prisma from "app/db.server";

export async function hasActiveSubscription(shopId: string): Promise<boolean> {
  try {
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shopId,
        status: "active",
      },
      select: {
        configuration: true,
      },
    });

    if (!billingPlan?.configuration) {
      return false;
    }

    const config = billingPlan.configuration as any;
    return config.subscription_id && config.subscription_status === "active";
  } catch (error) {
    console.error("❌ Error checking subscription status:", error);
    return false;
  }
}
