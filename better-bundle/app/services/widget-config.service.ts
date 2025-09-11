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
  return prisma.widgetConfiguration.upsert({
    where: { shopId: shop.id },
    update: {},
    create: {
      shopId: shop.id,
      isActive: true,
      layoutStyle: "grid",
      gridColumns: 3,
      useThemeColors: true,
      productPageEnabled: true,
      productPageTitle: "You might also like",
      productPageLimit: 6,
      productPageShowPrices: true,
      productPageShowReasons: true,
      cartPageEnabled: true,
      cartPageTitle: "Frequently bought together",
      cartPageLimit: 4,
      cartPageShowPrices: true,
      cartPageShowReasons: true,
      homepageEnabled: false,
      homepageTitle: "Popular products",
      homepageLimit: 8,
      homepageShowPrices: true,
      homepageShowReasons: false,
      collectionPageEnabled: true,
      collectionPageTitle: "Similar products",
      collectionPageLimit: 6,
      collectionPageShowPrices: true,
      collectionPageShowReasons: true,
      searchPageEnabled: true,
      searchPageTitle: "You might also like",
      searchPageLimit: 6,
      searchPageShowPrices: true,
      searchPageShowReasons: true,
      blogPageEnabled: false,
      blogPageTitle: "Featured products",
      blogPageLimit: 4,
      blogPageShowPrices: true,
      blogPageShowReasons: false,
      checkoutPageEnabled: false,
      checkoutPageTitle: "Last chance to add",
      checkoutPageLimit: 3,
      checkoutPageShowPrices: true,
      checkoutPageShowReasons: false,
      accountPageEnabled: false,
      accountPageTitle: "Recommended for you",
      accountPageLimit: 6,
      accountPageShowPrices: true,
      accountPageShowReasons: true,
      notFoundPageEnabled: false,
      notFoundPageTitle: "Popular products",
      notFoundPageLimit: 6,
      notFoundPageShowPrices: true,
      notFoundPageShowReasons: false,
      analyticsEnabled: true,
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

  return prisma.widgetConfiguration.update({
    where: { shopId: shop.id },
    data,
  });
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
