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
              }
              }
              }
              `);
    const shopData = await shopResponse.json();
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
  const shop = await prisma.shop.findUnique({
    where: { shopDomain },
  });
  return shop;
};

const getShopOnboardingCompleted = async (shopDomain: string) => {
  try {
    console.log("🔍 Checking shop onboarding status for:", shopDomain);
    const shop = await prisma.shop.findUnique({
      where: { shopDomain },
    });
    console.log("📊 Shop record found:", !!shop);
    if (!shop) {
      console.log("❌ No shop record found, onboarding not completed");
      return false;
    }
    const onboardingStatus = (shop as any)?.onboardingCompleted;
    console.log("📊 Onboarding status from DB:", onboardingStatus);
    console.log("📊 Final onboarding result:", !!onboardingStatus);
    return !!onboardingStatus; // Ensure boolean return
  } catch (error) {
    console.error("❌ Error getting shop onboarding completed:", error);
    return false;
  }
};

const createShopAndSetOnboardingCompleted = async (
  session: Session,
  shopData: any,
  tx?: any,
) => {
  const db = tx || prisma;
  const shop = await db.shop.upsert({
    where: { shopDomain: shopData.myshopifyDomain },
    update: {
      accessToken: session.accessToken,
      currencyCode: shopData.currencyCode,
      email: shopData.email,
      planType: shopData.plan.displayName,
      isActive: true,
    },
    create: {
      shopDomain: shopData.myshopifyDomain,
      accessToken: session.accessToken,
      currencyCode: shopData.currencyCode,
      email: shopData.email,
      planType: shopData.plan.displayName,
      isActive: true,
      onboardingCompleted: false as any, // Start as false, will be set to true later
    },
  });
  return shop;
};

const getBillingPlan = async (shopDomain: string) => {
  const billingPlan = await prisma.billingPlan.findFirst({
    where: { shopDomain, status: "active" },
  });
  return billingPlan;
};

const activateTrialBillingPlan = async (
  shopDomain: string,
  shopRecord: any,
  tx?: any,
) => {
  const db = tx || prisma;
  const billingPlan = await db.billingPlan.upsert({
    where: { shopId: shopRecord.id },
    update: {
      status: "active",
      configuration: {
        usage_based: true,
        trial_active: true,
        trial_threshold: 200.0,
        trial_revenue: 0.0,
        revenue_share_rate: 0.03,
        capped_amount: 1000.0,
        currency: shopRecord.currencyCode,
        subscription_pending: true,
      },
      isTrialActive: true,
      trialThreshold: 200.0,
      trialRevenue: 0.0,
    },
    create: {
      shopId: shopRecord.id,
      shopDomain: shopDomain,
      name: "Trial Plan",
      type: "usage_based",
      status: "active",
      configuration: {
        usage_based: true,
        trial_active: true,
        trial_threshold: 200.0,
        trial_revenue: 0.0,
        revenue_share_rate: 0.03,
        capped_amount: 1000.0,
        currency: shopRecord.currencyCode,
        subscription_pending: true,
      },
      effectiveFrom: new Date(),
      isTrialActive: true,
      trialThreshold: 200.0,
      trialRevenue: 0.0,
    },
  });
  return billingPlan;
};

const markOnboardingCompleted = async (shopDomain: string, tx?: any) => {
  const db = tx || prisma;
  await db.shop.update({
    where: { shopDomain },
    data: { onboardingCompleted: true } as any,
  });
};

const activateAtlasWebPixel = async (admin: any, shopDomain: string) => {
  try {
    // Get the backend URL from environment or use a default
    const backendUrl = process.env.BACKEND_URL;

    const webPixelSettings = {
      backend_url: backendUrl,
    };

    // First, try to create the web pixel
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

    // If creation failed due to "TAKEN" error, try to update existing web pixel
    const hasTakenError =
      createResponseJson.data?.webPixelCreate?.userErrors?.some(
        (error: any) => error.code === "TAKEN",
      );

    if (hasTakenError) {
      console.log("🔄 Web pixel already exists, attempting to update...");

      // First, get the existing web pixel ID
      const query = `
        query {
          webPixels(first: 1) {
            edges {
              node {
                id
                settings
              }
            }
          }
        }
      `;

      const queryResponse = await admin.graphql(query);
      const queryResponseJson = await queryResponse.json();

      if (queryResponseJson.data?.webPixels?.edges?.length > 0) {
        const webPixelId = queryResponseJson.data.webPixels.edges[0].node.id;

        // Update the existing web pixel
        const updateMutation = `
          mutation webPixelUpdate($id: ID!, $webPixel: WebPixelInput!) {
            webPixelUpdate(id: $id, webPixel: $webPixel) {
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

        const updateResponse = await admin.graphql(updateMutation, {
          variables: {
            id: webPixelId,
            webPixel: {
              settings: JSON.stringify(webPixelSettings),
            },
          },
        });

        const updateResponseJson = await updateResponse.json();

        if (
          updateResponseJson.data?.webPixelUpdate?.userErrors?.length === 0 &&
          updateResponseJson.data?.webPixelUpdate?.webPixel
        ) {
          console.log(
            "✅ Atlas web pixel updated successfully:",
            updateResponseJson.data.webPixelUpdate.webPixel.id,
          );
          return updateResponseJson.data.webPixelUpdate.webPixel;
        } else {
          console.error(
            "❌ Web pixel update errors:",
            updateResponseJson.data?.webPixelUpdate?.userErrors,
          );
        }
      }
    } else {
      // Other creation errors
      console.error(
        "❌ Web pixel creation errors:",
        createResponseJson.data?.webPixelCreate?.userErrors,
      );
    }

    throw new Error("Failed to create or update web pixel");
  } catch (error) {
    console.error("❌ Failed to activate Atlas web pixel:", error);
    // Don't throw the error to prevent breaking the entire afterAuth flow
    // The app can still function without the web pixel
  }
};

export {
  getShop,
  getShopOnboardingCompleted,
  createShopAndSetOnboardingCompleted,
  getBillingPlan,
  activateTrialBillingPlan,
  activateAtlasWebPixel,
  getShopInfoFromShopify,
  markOnboardingCompleted,
};
