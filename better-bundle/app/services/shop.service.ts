import prisma from "../db.server";
import logger from "../utils/logger";

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

export {
  getShopOnboardingCompleted,
};
