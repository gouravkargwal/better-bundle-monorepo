import prisma from "../db.server";

type ContextKey =
  | "product_page"
  | "cart"
  | "homepage"
  | "collection"
  | "search"
  | "blog"
  | "checkout"
  | "account"
  | "not_found";

export async function getShopByDomain(shopDomain: string) {
  return prisma.shop.findUnique({ where: { shopDomain } });
}

export async function getWidgetConfiguration(shopDomain: string) {
  const shop = await getShopByDomain(shopDomain);
  if (!shop) return null;
  return prisma.widgetConfiguration.findUnique({ where: { shopId: shop.id } });
}

export async function createDefaultConfiguration(shopDomain: string) {
  let shop = await getShopByDomain(shopDomain);
  if (!shop) throw new Error("Shop not found");

  // Let Prisma schema defaults handle all the default values
  return prisma.widgetConfiguration.upsert({
    where: { shopId: shop.id },
    update: {},
    create: {
      shopId: shop.id,
      // All other fields will use their schema defaults
    },
  });
}

export async function updateWidgetConfiguration(
  shopDomain: string,
  data: Partial<
    Parameters<typeof prisma.widgetConfiguration.update>[0]["data"]
  >,
) {
  const shop = await getShopByDomain(shopDomain);
  if (!shop) throw new Error("Shop not found");

  try {
    // Add timestamp for consistency tracking
    const updateData = {
      ...data,
      updatedAt: new Date(),
    };

    const result = await prisma.widgetConfiguration.update({
      where: { shopId: shop.id },
      data: updateData,
    });

    console.log(`✅ Widget configuration updated for shop: ${shopDomain}`, {
      updatedFields: Object.keys(data),
      timestamp: result.updatedAt,
    });

    return result;
  } catch (error) {
    console.error(
      `❌ Error updating widget configuration for shop: ${shopDomain}`,
      error,
    );

    // Check if it's a record not found error
    if (
      error instanceof Error &&
      error.message.includes("Record to update not found")
    ) {
      // Try to create the configuration if it doesn't exist
      console.log(
        `🔄 Configuration not found, creating default for shop: ${shopDomain}`,
      );
      return await createDefaultConfiguration(shopDomain);
    }

    throw error;
  }
}

export function getContextSettings(config: any, context: ContextKey) {
  switch (context) {
    case "product_page":
      return {
        enabled: config.productPageEnabled,
        title: config.productPageTitle,
        limit: config.productPageLimit,
        showPrices: config.productPageShowPrices,
        showReasons: config.productPageShowReasons,
      };
    case "cart":
      return {
        enabled: config.cartPageEnabled,
        title: config.cartPageTitle,
        limit: config.cartPageLimit,
        showPrices: config.cartPageShowPrices,
        showReasons: config.cartPageShowReasons,
      };
    case "homepage":
      return {
        enabled: config.homepageEnabled,
        title: config.homepageTitle,
        limit: config.homepageLimit,
        showPrices: config.homepageShowPrices,
        showReasons: config.homepageShowReasons,
      };
    case "collection":
      return {
        enabled: config.collectionPageEnabled,
        title: config.collectionPageTitle,
        limit: config.collectionPageLimit,
        showPrices: config.collectionPageShowPrices,
        showReasons: config.collectionPageShowReasons,
      };
    case "search":
      return {
        enabled: config.searchPageEnabled,
        title: config.searchPageTitle,
        limit: config.searchPageLimit,
        showPrices: config.searchPageShowPrices,
        showReasons: config.searchPageShowReasons,
      };
    case "blog":
      return {
        enabled: config.blogPageEnabled,
        title: config.blogPageTitle,
        limit: config.blogPageLimit,
        showPrices: config.blogPageShowPrices,
        showReasons: config.blogPageShowReasons,
      };
    case "checkout":
      return {
        enabled: config.checkoutPageEnabled,
        title: config.checkoutPageTitle,
        limit: config.checkoutPageLimit,
        showPrices: config.checkoutPageShowPrices,
        showReasons: config.checkoutPageShowReasons,
      };
    case "account":
      return {
        enabled: config.accountPageEnabled,
        title: config.accountPageTitle,
        limit: config.accountPageLimit,
        showPrices: config.accountPageShowPrices,
        showReasons: config.accountPageShowReasons,
      };
    case "not_found":
      return {
        enabled: config.notFoundPageEnabled,
        title: config.notFoundPageTitle,
        limit: config.notFoundPageLimit,
        showPrices: config.notFoundPageShowPrices,
        showReasons: config.notFoundPageShowReasons,
      };
    default:
      return {
        enabled: true,
        title: "You might also like",
        limit: 6,
        showPrices: true,
        showReasons: true,
      };
  }
}
