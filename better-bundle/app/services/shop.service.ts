import prisma from "app/db.server";
import type { Session } from "@shopify/shopify-api";
import logger from "../utils/logger";

const getShopInfoFromShopify = async (admin: any) => {
  try {
    const shopResponse = await admin.graphql(`
      query {
        shop {
          id
          name
          myshopifyDomain
          primaryDomain {
            host
            url
          }
          email
          currencyCode
          plan {
            displayName
            shopifyPlus
          }
        }
      }
    `);
    const shopData = await shopResponse.json();
    if (shopData.errors) {
      throw new Error("GraphQL errors: " + JSON.stringify(shopData.errors));
    }
    const shop = shopData.data?.shop;
    if (!shop) {
      throw new Error("Failed to fetch shop data from Shopify API");
    }
    return shop;
  } catch (error) {
    logger.error({ error }, "Error getting shop info from Shopify");
    throw new Error("Failed to fetch shop data from Shopify API");
  }
};

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
    const onboardingStatus = (shop as any)?.onboarding_completed;
    return !!onboardingStatus; // Ensure boolean return
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

const createShopAndSetOnboardingCompleted = async (
  session: Session,
  shopData: any,
  tx?: any,
) => {
  const db = tx || prisma;

  // Check if this is a reinstall (shop exists but was inactive)
  const existingShop = await db.shops.findUnique({
    where: { shop_domain: shopData.myshopifyDomain },
    include: {
      // Include billing plan to check if it was previously active
    },
  });

  const isReinstall = existingShop && !existingShop.is_active;

  const shop = await db.shops.upsert({
    where: { shop_domain: shopData.myshopifyDomain },
    update: {
      access_token: session.accessToken,
      currency_code: shopData.currencyCode,
      email: shopData.email,
      plan_type: shopData.plan.displayName,
      shopify_plus: shopData.plan.shopifyPlus || false,
      is_active: true,
      // For reinstalls, preserve onboarding status if it was completed
      ...(isReinstall && existingShop.onboarding_completed
        ? {}
        : { onboarding_completed: false as any }),
    },
    create: {
      shop_domain: shopData.myshopifyDomain,
      access_token: session.accessToken,
      currency_code: shopData.currencyCode,
      email: shopData.email,
      plan_type: shopData.plan.displayName,
      shopify_plus: shopData.plan.shopifyPlus || false,
      is_active: true,
      onboarding_completed: false as any, // Start as false, will be set to true later
    },
  });

  return shop;
};

const getShopSubscription = async (shopDomain: string) => {
  const billingPlan = await prisma.shop_subscriptions.findFirst({
    where: { shop_domain: shopDomain, status: "ACTIVE" },
  });
  return billingPlan;
};

const markOnboardingCompleted = async (shopDomain: string, tx?: any) => {
  const db = tx || prisma;
  await db.shops.update({
    where: { shop_domain: shopDomain },
    data: { onboarding_completed: true } as any,
  });
};

const activateAtlasWebPixel = async (admin: any, shopDomain: string) => {
  try {
    // Try to create the web pixel
    const createMutation = `
      mutation webPixelCreate($webPixel: WebPixelInput!) {
        webPixelCreate(webPixel: $webPixel) {
          userErrors {
            code
            field
            message
          }
          webPixel {
            id
            settings
          }
        }
      }
    `;

    const createResponse = await admin.graphql(createMutation, {
      variables: {
        webPixel: {
          settings: "{}", // Must be a JSON string, even if empty
        },
      },
    });

    const createResponseJson = await createResponse.json();

    // Check if creation was successful
    if (
      createResponseJson.data?.webPixelCreate?.userErrors?.length === 0 &&
      createResponseJson.data?.webPixelCreate?.webPixel
    ) {
      return createResponseJson.data.webPixelCreate.webPixel;
    }

    // If creation failed due to "TAKEN" error, the pixel already exists
    const hasTakenError =
      createResponseJson.data?.webPixelCreate?.userErrors?.some(
        (error: any) => error.code === "TAKEN",
      );

    if (hasTakenError) {
      // Since we can't query existing pixels due to API limitations,
      // we'll assume it's working if we get a TAKEN error
      return { id: "existing" };
    }

    // Log other creation errors but don't fail the entire flow
    const errors = createResponseJson.data?.webPixelCreate?.userErrors || [];
    if (errors.length > 0) {
      logger.warn(
        {
          errors: errors.map((e: any) => `${e.code}: ${e.message}`).join(", "),
        },
        "Web pixel creation had issues",
      );
    }

    return null;
  } catch (error) {
    logger.error({ error }, "Failed to activate Atlas web pixel");
    // Don't throw the error to prevent breaking the entire afterAuth flow
    // The app can still function without the web pixel
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

    // 2. Deactivate all billing plans for this shop
    const updatedSubscriptions = await prisma.shop_subscriptions.updateMany({
      where: { shop_id: updatedShops.id, status: "ACTIVE" },
      data: {
        status: "CANCELLED",
        effective_to: new Date(),
        updated_at: new Date(),
      },
    });

    // 3. Create billing event to track the deactivation
    await prisma.shop_subscriptions.findFirst({
      where: { shop_id: updatedShops.id, status: "ACTIVE" },
      select: { id: true, shop_id: true },
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
  createShopAndSetOnboardingCompleted,
  getShopSubscription,
  activateAtlasWebPixel,
  getShopInfoFromShopify,
  markOnboardingCompleted,
  deactivateShopBilling,
};
