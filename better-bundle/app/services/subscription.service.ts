import prisma from "app/db.server";
import logger from "../utils/logger";

/**
 * Check if a shop has an active flat fee subscription
 */
export async function hasActiveSubscription(shopId: string): Promise<boolean> {
  try {
    const subscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopId,
        is_active: true,
        status: "ACTIVE",
        subscription_type: "PAID",
      },
    });

    return !!subscription;
  } catch (error) {
    logger.error({ error }, "Error checking subscription status");
    return false;
  }
}

/**
 * Check if a shop has an active subscription or is in trial
 */
export async function hasActiveSubscriptionOrTrial(
  shopId: string,
): Promise<boolean> {
  try {
    const subscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopId,
        is_active: true,
        status: {
          in: ["ACTIVE", "TRIAL"],
        },
      },
    });

    return !!subscription;
  } catch (error) {
    logger.error({ error }, "Error checking subscription/trial status");
    return false;
  }
}
