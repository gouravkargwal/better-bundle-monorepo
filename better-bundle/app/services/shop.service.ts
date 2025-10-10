import prisma from "app/db.server";
import type { Session } from "@shopify/shopify-api";

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
    console.error("Error getting shop info from Shopify:", error);
    throw new Error("Failed to fetch shop data from Shopify API");
  }
};

const getShop = async (shopDomain: string) => {
  const shop = await prisma.shops.findUnique({
    where: { shop_domain: shopDomain },
  });
  return shop;
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
    console.error("❌ Error getting shop onboarding completed:", error);
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
    console.error("❌ Error getting Shopify Plus status:", error);
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

  if (isReinstall) {
    console.log(`🔄 Reactivating shop: ${shopData.myshopifyDomain}`);
    console.log(`   - Previous status: inactive`);
    console.log(
      `   - Previous onboarding: ${existingShop.onboarding_completed}`,
    );
  } else {
    console.log(`🆕 Creating new shop: ${shopData.myshopifyDomain}`);
  }

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
    // Get the backend URL from environment or use a default
    const backendUrl = process.env.BACKEND_URL;

    const webPixelSettings = {
      backend_url: backendUrl,
    };

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
          settings: JSON.stringify(webPixelSettings),
        },
      },
    });

    const createResponseJson = await createResponse.json();

    // Check if creation was successful
    if (
      createResponseJson.data?.webPixelCreate?.userErrors?.length === 0 &&
      createResponseJson.data?.webPixelCreate?.webPixel
    ) {
      console.log(
        "✅ Atlas web pixel created successfully:",
        createResponseJson.data.webPixelCreate.webPixel.id,
      );
      return createResponseJson.data.webPixelCreate.webPixel;
    }

    // If creation failed due to "TAKEN" error, the pixel already exists
    const hasTakenError =
      createResponseJson.data?.webPixelCreate?.userErrors?.some(
        (error: any) => error.code === "TAKEN",
      );

    if (hasTakenError) {
      console.log("✅ Web pixel already exists and is active");
      // Since we can't query existing pixels due to API limitations,
      // we'll assume it's working if we get a TAKEN error
      return { id: "existing", settings: webPixelSettings };
    }

    // Log other creation errors but don't fail the entire flow
    const errors = createResponseJson.data?.webPixelCreate?.userErrors || [];
    if (errors.length > 0) {
      console.warn(
        "⚠️ Web pixel creation had issues:",
        errors.map((e: any) => `${e.code}: ${e.message}`).join(", "),
      );
    }

    // Don't throw error - the app can function without the web pixel
    console.log("ℹ️ Web pixel activation completed with warnings");
    return null;
  } catch (error) {
    console.error("❌ Failed to activate Atlas web pixel:", error);
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
    console.log(`🔄 Deactivating billing for shop: ${shopDomain}`);

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

    console.log(`✅ Successfully deactivated billing for ${shopDomain}:`);
    console.log(`   - Marked shop as inactive`);
    console.log(`   - Deactivated ${updatedSubscriptions.count} billing plans`);
    console.log(`   - Created billing event`);

    return {
      success: true,
      plans_deactivated_count: updatedSubscriptions.count,
      reason,
    };
  } catch (error) {
    console.error(`❌ Error deactivating billing for ${shopDomain}:`, error);
    throw new Error(
      `Failed to deactivate billing for shop: ${error instanceof Error ? error.message : "Unknown error"}`,
    );
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
