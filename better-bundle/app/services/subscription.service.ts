import prisma from "app/db.server";
import logger from "../utils/logger";

/**
 * Check whether a shop has an active flat-fee subscription.
 *
 * With the flat-fee model, the source of truth is the shop's
 * `shop_subscriptions` row (linked to `subscription_plans`), confirmed by
 * Shopify's own subscription status when available.
 */
export async function hasActiveSubscription(shopId: string): Promise<boolean> {
  try {
    const subscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopId,
        is_active: true,
        status: "ACTIVE",
      },
      include: { subscription_plans: true },
    });

    return Boolean(subscription);
  } catch (error) {
    logger.error({ error }, "Error checking subscription status");
    return false;
  }
}
