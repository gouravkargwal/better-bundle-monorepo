import prisma from "app/db.server";
import type { Session } from "@shopify/shopify-api";
import { getTrialThresholdInShopCurrency } from "../utils/currency-converter";

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
  const shop = await prisma.shops.findUnique({
    where: { shop_domain: shopDomain },
  });
  return shop;
};

const getShopOnboardingCompleted = async (shopDomain: string) => {
  try {
    console.log("🔍 Checking shop onboarding status for:", shopDomain);
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: shopDomain },
    });
    console.log("📊 Shop record found:", !!shop);
    if (!shop) {
      console.log("❌ No shop record found, onboarding not completed");
      return false;
    }
    const onboardingStatus = (shop as any)?.onboarding_completed;
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
      currency_code: shopData.currency_code,
      email: shopData.email,
      plan_type: shopData.plan.displayName,
      is_active: true,
      // For reinstalls, preserve onboarding status if it was completed
      ...(isReinstall && existingShop.onboarding_completed
        ? {}
        : { onboarding_completed: false as any }),
    },
    create: {
      shop_domain: shopData.myshopifyDomain,
      access_token: session.accessToken,
      currency_code: shopData.currency_code,
      email: shopData.email,
      plan_type: shopData.plan.displayName,
      is_active: true,
      onboarding_completed: false as any, // Start as false, will be set to true later
    },
  });

  // Create billing event for reactivation if it's a reinstall
  if (isReinstall) {
    await db.billing_events.create({
      data: {
        shop_id: shop.id,
        type: "billing_reactivated",
        data: {
          reason: "app_reinstalled",
          reactivated_at: new Date().toISOString(),
          shop_domain: shopData.myshopifyDomain,
          preserved_onboarding: existingShop.onboarding_completed,
        },
        metadata: {
          processed_at: new Date().toISOString(),
          is_reinstall: true,
        },
        occurred_at: new Date(),
      },
    });
  }

  return shop;
};

const getBillingPlan = async (shopDomain: string) => {
  const billingPlan = await prisma.billing_plans.findFirst({
    where: { shop_domain: shopDomain, status: "active" },
  });
  return billingPlan;
};

const activateTrialBillingPlan = async (
  shopDomain: string,
  shopRecord: any,
  tx?: any,
) => {
  const db = tx || prisma;

  // Fixed $200 USD trial threshold (industry standard)
  const TRIAL_THRESHOLD_USD = 200.0;

  // Convert to shop currency for display and storage
  const trialThresholdInShopCurrency = await getTrialThresholdInShopCurrency(
    shopRecord.currency_code,
  );

  const billingPlan = await db.billing_plans.upsert({
    where: { shop_id: shopRecord.id },
    update: {
      status: "active",
      configuration: {
        usage_based: true,
        trial_active: true,
        trial_threshold: trialThresholdInShopCurrency,
        trial_revenue: 0.0,
        revenue_share_rate: 0.03,
        currency: shopRecord.currency_code,
        subscription_pending: true,
        trial_threshold_usd: TRIAL_THRESHOLD_USD,
      },
      is_trial_active: true,
      trial_threshold: trialThresholdInShopCurrency,
      trial_revenue: 0.0,
    },
    create: {
      shop_id: shopRecord.id,
      shop_domain: shopDomain,
      name: "Trial Plan",
      type: "usage_based",
      status: "active",
      configuration: {
        usage_based: true,
        trial_active: true,
        trial_threshold: trialThresholdInShopCurrency,
        trial_revenue: 0.0,
        revenue_share_rate: 0.03,
        currency: shopRecord.currency_code,
        subscription_pending: true,
        trial_threshold_usd: TRIAL_THRESHOLD_USD,
      },
      effective_from: new Date(),
      is_trial_active: true,
      trial_threshold: trialThresholdInShopCurrency,
      trial_revenue: 0.0,
    },
  });

  console.log(`✅ Trial billing plan activated for ${shopDomain}:`);
  console.log(`   - Trial threshold: $${TRIAL_THRESHOLD_USD} USD`);
  console.log(
    `   - Trial threshold in shop currency: ${trialThresholdInShopCurrency} ${shopRecord.currency_code}`,
  );
  console.log(`   - Shop currency: ${shopRecord.currency_code}`);
  console.log(`   - Revenue share rate: 3%`);

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

const deactivateShopBilling = async (
  shopDomain: string,
  reason: string = "app_uninstalled",
) => {
  try {
    console.log(`🔄 Deactivating billing for shop: ${shopDomain}`);

    // 1. Mark shop as inactive
    await prisma.shops.updateMany({
      where: { shop_domain: shopDomain },
      data: {
        is_active: false,
        updated_at: new Date(),
      },
    });

    // 2. Deactivate all billing plans for this shop
    const updatedPlans = await prisma.billing_plans.updateMany({
      where: { shop_domain: shopDomain },
      data: {
        status: "inactive",
        effective_until: new Date(),
        updated_at: new Date(),
      },
    });

    // 3. Create billing event to track the deactivation
    const billingPlan = await prisma.billing_plans.findFirst({
      where: { shop_domain: shopDomain },
      select: { id: true },
    });

    if (billingPlan) {
      await prisma.billing_events.create({
        data: {
          shop_id: billingPlan.id,
          type: "billing_suspended",
          data: {
            reason,
            deactivated_at: new Date().toISOString(),
            shop_domain: billingPlan.shop_domain,
          },
          metadata: {
            processed_at: new Date().toISOString(),
            plans_affected_count: updatedPlans.count,
          },
          occurred_at: new Date(),
        },
      });
    }

    console.log(`✅ Successfully deactivated billing for ${shopDomain}:`);
    console.log(`   - Marked shop as inactive`);
    console.log(`   - Deactivated ${updatedPlans.count} billing plans`);
    console.log(`   - Created billing event`);

    return {
      success: true,
      plans_deactivated_count: updatedPlans.count,
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
  createShopAndSetOnboardingCompleted,
  getBillingPlan,
  activateTrialBillingPlan,
  activateAtlasWebPixel,
  getShopInfoFromShopify,
  markOnboardingCompleted,
  deactivateShopBilling,
};
