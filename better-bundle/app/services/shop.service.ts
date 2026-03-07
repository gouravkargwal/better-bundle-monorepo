import prisma from "../db.server";
import logger from "../utils/logger";

const getShop = async (shopDomain: string) => {
  try {
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: shopDomain },
    });
    return shop;
  } catch (error) {
    logger.error({ error }, "Error getting shop");
    return null;
  }
};

const getShopOnboardingCompleted = async (shopDomain: string) => {
  try {
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: shopDomain },
    });
    if (!shop) {
      return false;
    }
    return !!shop.onboarding_completed;
  } catch (error) {
    logger.error({ error }, "Error getting shop onboarding completed");
    return false;
  }
};

const getShopifyPlusStatus = async (shopDomain: string) => {
  try {
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: shopDomain },
      select: { shopify_plus: true, plan_type: true },
    });
    if (!shop) {
      return false;
    }
    return shop.shopify_plus || false;
  } catch (error) {
    logger.error({ error }, "Error getting Shopify Plus status");
    return false;
  }
};

const getShopSubscription = async (shopDomain: string) => {
  try {
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: shopDomain },
      select: { id: true },
    });
    if (!shop) return null;
    const billingPlan = await prisma.shop_subscriptions.findFirst({
      where: { shop_id: shop.id, status: "ACTIVE" },
    });
    return billingPlan;
  } catch (error) {
    logger.error({ error, shopDomain }, "Error getting shop subscription");
    return null;
  }
};

const deactivateShopBilling = async (
  shopDomain: string,
  reason: string = "app_uninstalled",
) => {
  try {
    // 1. Mark shop as inactive
    const updatedShops = await prisma.shops.update({
      where: { shop_domain: shopDomain },
      data: {
        is_active: false,
        updated_at: new Date(),
      },
    });

    // 2. Deactivate all non-terminal billing plans for this shop
    const updatedSubscriptions = await prisma.shop_subscriptions.updateMany({
      where: {
        shop_id: updatedShops.id,
        status: { in: ["ACTIVE", "TRIAL", "PENDING_APPROVAL", "SUSPENDED"] as any },
      },
      data: {
        status: "CANCELLED",
        cancelled_at: new Date(),
        updated_at: new Date(),
      },
    });

    return {
      success: true,
      plans_deactivated_count: updatedSubscriptions.count,
      reason,
    };
  } catch (error) {
    logger.error({ error, shopDomain }, "Error deactivating billing for shop");
    throw new Error("Failed to deactivate billing for shop");
  }
};

export {
  getShop,
  getShopOnboardingCompleted,
  getShopifyPlusStatus,
  getShopSubscription,
  deactivateShopBilling,
};
