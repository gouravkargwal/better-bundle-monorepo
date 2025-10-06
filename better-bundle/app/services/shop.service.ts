import prisma from "app/db.server";
import type { Session } from "@shopify/shopify-api";
import { getTrialThresholdInShopCurrency } from "../utils/currency-converter";
import { createUsageBasedSubscription } from "./subscription.service";

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
      select: { id: true, shop_id: true },
    });

    if (billingPlan) {
      await prisma.billing_events.create({
        data: {
          plan_id: billingPlan.id,
          shop_id: billingPlan.shop_id,
          type: "billing_suspended",
          data: {
            reason,
            deactivated_at: new Date().toISOString(),
            shop_domain: shopDomain,
          },
          billing_metadata: {
            processed_at: new Date().toISOString(),
            plans_affected_count: updatedPlans.count,
          },
          occurred_at: new Date(),
          processed_at: new Date(),
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

const handleTrialCompletion = async (
  session: Session,
  admin: any,
  shopId: string,
  shopDomain: string,
  finalRevenue: number,
  currencyCode: string = "USD",
) => {
  try {
    console.log(
      `🎉 Trial completed for shop ${shopDomain} with revenue $${finalRevenue}`,
    );

    // 1. Update billing plan to mark trial as completed
    await prisma.billing_plans.updateMany({
      where: {
        shop_id: shopId,
        status: "active",
        is_trial_active: true,
      },
      data: {
        is_trial_active: false,
        trial_revenue: finalRevenue,
        configuration: {
          trial_active: false,
          trial_completed_at: new Date().toISOString(),
          trial_completion_revenue: finalRevenue,
          services_stopped: true,
          consent_required: true,
          subscription_required: true,
          billing_suspended: true,
        },
      },
    });

    // 2. Create usage-based subscription
    console.log(`🔄 Creating usage-based subscription for shop ${shopDomain}`);
    const subscription = await createUsageBasedSubscription(
      session,
      admin,
      shopId,
      shopDomain,
      currencyCode,
    );

    if (subscription) {
      console.log(`✅ Usage-based subscription created: ${subscription.id}`);

      // Update billing plan with subscription details
      await prisma.billing_plans.updateMany({
        where: {
          shop_id: shopId,
          status: "active",
        },
        data: {
          configuration: {
            subscription_id: subscription.id,
            subscription_status: "PENDING",
            subscription_created_at: new Date().toISOString(),
            usage_based: true,
            capped_amount: "1000",
            currency: currencyCode,
            trial_active: false,
            trial_completed_at: new Date().toISOString(),
            trial_completion_revenue: finalRevenue,
            services_stopped: true,
            consent_required: true,
            subscription_required: true,
            billing_suspended: true,
          },
        },
      });

      // Create billing event for trial completion
      await prisma.billing_events.create({
        data: {
          shop_id: shopId,
          type: "trial_completed",
          data: {
            final_revenue: finalRevenue,
            completed_at: new Date().toISOString(),
            subscription_id: subscription.id,
            subscription_created: true,
          },
          metadata: {
            trial_completion: true,
            final_revenue: finalRevenue,
            subscription_created: true,
          },
          occurred_at: new Date(),
        },
      });

      return {
        success: true,
        subscription_created: true,
        subscription_id: subscription.id,
        final_revenue: finalRevenue,
      };
    } else {
      console.error(`❌ Failed to create subscription for shop ${shopDomain}`);

      // Create billing event for trial completion without subscription
      await prisma.billing_events.create({
        data: {
          shop_id: shopId,
          type: "trial_completed_no_subscription",
          data: {
            final_revenue: finalRevenue,
            completed_at: new Date().toISOString(),
            subscription_created: false,
            error: "Failed to create subscription",
          },
          metadata: {
            trial_completion: true,
            final_revenue: finalRevenue,
            subscription_created: false,
          },
          occurred_at: new Date(),
        },
      });

      return {
        success: false,
        subscription_created: false,
        error: "Failed to create subscription",
        final_revenue: finalRevenue,
      };
    }
  } catch (error) {
    console.error(
      `❌ Error handling trial completion for shop ${shopDomain}:`,
      error,
    );

    // Create billing event for error
    await prisma.billing_events.create({
      data: {
        shop_id: shopId,
        type: "trial_completion_error",
        data: {
          final_revenue: finalRevenue,
          error: error instanceof Error ? error.message : "Unknown error",
          occurred_at: new Date().toISOString(),
        },
        metadata: {
          trial_completion: true,
          final_revenue: finalRevenue,
          error: true,
        },
        occurred_at: new Date(),
      },
    });

    throw new Error(
      `Failed to handle trial completion: ${error instanceof Error ? error.message : "Unknown error"}`,
    );
  }
};

// In activateTrialBillingPlan function:

const activateTrialBillingPlan = async (
  shopDomain: string,
  shopRecord: any,
  tx?: any,
) => {
  const db = tx || prisma;

  // Get trial config for the shop's currency
  const { getTrialConfig } = await import("../services/trial-config.service");
  const trialConfig = await getTrialConfig(
    shopDomain,
    shopRecord.currency_code,
  );

  // Use trial config USD threshold, throw error if not found
  if (!trialConfig?.threshold_usd) {
    throw new Error(
      `No trial threshold configured for currency: ${shopRecord.currency_code}`,
    );
  }
  const TRIAL_THRESHOLD_USD = trialConfig.threshold_usd;

  const trialThresholdInShopCurrency = await getTrialThresholdInShopCurrency(
    shopRecord.currency_code,
    TRIAL_THRESHOLD_USD,
  );

  const billingPlan = await db.billing_plans.upsert({
    where: { shop_id: shopRecord.id },
    update: {
      status: "active",
      is_trial_active: true,
      trial_threshold: trialThresholdInShopCurrency,
      trial_revenue: 0.0,
      trial_usage_records_count: 0,
      configuration: {
        pattern: "trial_without_consent", // ✅ Pattern 1
        trial_active: true,
        trial_threshold: trialThresholdInShopCurrency,
        trial_threshold_usd: TRIAL_THRESHOLD_USD,
        trial_revenue: 0.0,
        revenue_share_rate: 0.03,
        currency: shopRecord.currency_code,
        post_trial_capped_amount: 1000.0,
        subscription_required_after_trial: true, // ✅ Key flag
      },
    },
    create: {
      shop_id: shopRecord.id,
      shop_domain: shopDomain,
      name: "Free Trial (Usage-Based)",
      type: "trial",
      status: "active",
      is_trial_active: true,
      trial_threshold: trialThresholdInShopCurrency,
      trial_revenue: 0.0,
      trial_usage_records_count: 0,
      effective_from: new Date(),
      configuration: {
        pattern: "trial_without_consent",
        trial_active: true,
        trial_threshold: trialThresholdInShopCurrency,
        trial_threshold_usd: TRIAL_THRESHOLD_USD,
        trial_revenue: 0.0,
        revenue_share_rate: 0.03,
        currency: shopRecord.currency_code,
        post_trial_capped_amount: 1000.0,
        subscription_required_after_trial: true,
      },
    },
  });

  console.log(`✅ Pattern 1 trial activated for ${shopDomain}:`);
  console.log(`   - NO upfront subscription required`);
  console.log(`   - Trial threshold: $${TRIAL_THRESHOLD_USD} USD`);
  console.log(`   - Services active immediately`);
  console.log(`   - Subscription required after trial`);

  return billingPlan;
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
  handleTrialCompletion,
};
