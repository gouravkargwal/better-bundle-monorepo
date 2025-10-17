// features/onboarding/services/onboarding.service.ts
import prisma from "../../../db.server";
import { getCurrencySymbol } from "../../../utils/currency";
import { KafkaProducerService } from "../../../services/kafka/kafka-producer.service";

export class OnboardingService {
  async getOnboardingData(shopDomain: string, admin: any) {
    // Get shop info from Shopify
    const shopData = await this.getShopInfoFromShopify(admin);

    // Get pricing tier configuration
    const pricingTier = await this.getPricingTierConfig(
      shopDomain,
      shopData.currencyCode,
    );

    return {
      pricingTier,
    };
  }

  async completeOnboarding(session: any, admin: any) {
    // Get shop data from Shopify
    const shopData = await this.getShopInfoFromShopify(admin);

    // Complete onboarding in transaction
    await this.completeOnboardingTransaction(session, shopData);

    // Activate web pixel
    await this.activateWebPixel(admin, session.shop);

    // Trigger analysis
    await this.triggerAnalysis(session.shop);
  }

  private async getShopInfoFromShopify(admin: any) {
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
  }

  private async getPricingTierConfig(shopDomain: string, currencyCode: string) {
    // Get default subscription plan
    const defaultPlan = await prisma.subscription_plans.findFirst({
      where: {
        is_active: true,
        is_default: true,
      },
    });

    if (!defaultPlan) {
      throw new Error("No default subscription plan found");
    }

    // Get pricing tier for currency
    const pricingTier = await prisma.pricing_tiers.findFirst({
      where: {
        subscription_plan_id: defaultPlan.id,
        currency: currencyCode,
        is_active: true,
        is_default: true,
      },
    });

    if (!pricingTier) {
      throw new Error(`No pricing tier found for currency: ${currencyCode}`);
    }

    return {
      symbol: getCurrencySymbol(currencyCode),
      threshold_amount: pricingTier.trial_threshold_amount,
    };
  }

  private async completeOnboardingTransaction(session: any, shopData: any) {
    return await prisma.$transaction(async (tx) => {
      // Create or update shop
      const shop = await this.createOrUpdateShop(session, shopData, tx);

      // Activate trial billing plan
      await this.activateTrialBillingPlan(session.shop, shop, tx);

      // Mark onboarding as completed
      await this.markOnboardingCompleted(session.shop, tx);

      return shop;
    });
  }

  private async createOrUpdateShop(session: any, shopData: any, tx: any) {
    // Check if this is a reinstall
    const existingShop = await tx.shops.findUnique({
      where: { shop_domain: shopData.myshopifyDomain },
    });

    const isReinstall = existingShop && !existingShop.is_active;

    if (isReinstall) {
      console.log(`🔄 Reactivating shop: ${shopData.myshopifyDomain}`);
    } else {
      console.log(`🆕 Creating new shop: ${shopData.myshopifyDomain}`);
    }

    return await tx.shops.upsert({
      where: { shop_domain: shopData.myshopifyDomain },
      update: {
        access_token: session.accessToken,
        currency_code: shopData.currencyCode,
        email: shopData.email,
        plan_type: shopData.plan.displayName,
        is_active: true,
        shopify_plus:
          shopData.plan.displayName.includes("Plus") ||
          shopData.plan.displayName.includes("plus"),
        // For reinstalls, preserve onboarding status if it was completed
        ...(isReinstall && existingShop.onboarding_completed
          ? {}
          : { onboarding_completed: false }),
      },
      create: {
        shop_domain: shopData.myshopifyDomain,
        access_token: session.accessToken,
        currency_code: shopData.currencyCode,
        email: shopData.email,
        plan_type: shopData.plan.displayName,
        is_active: true,
        onboarding_completed: false,
        shopify_plus:
          shopData.plan.displayName.includes("Plus") ||
          shopData.plan.displayName.includes("plus"),
      },
    });
  }

  private async activateTrialBillingPlan(
    shopDomain: string,
    shopRecord: any,
    tx: any,
  ) {
    // Get default subscription plan
    const defaultPlan = await tx.subscription_plans.findFirst({
      where: {
        is_active: true,
        is_default: true,
      },
    });

    if (!defaultPlan) {
      throw new Error("No default subscription plan found");
    }

    // Get pricing tier for shop's currency
    const pricingTier = await tx.pricing_tiers.findFirst({
      where: {
        subscription_plan_id: defaultPlan.id,
        currency: shopRecord.currency_code,
        is_active: true,
        is_default: true,
      },
    });

    if (!pricingTier) {
      throw new Error(
        `No pricing tier found for currency: ${shopRecord.currency_code}`,
      );
    }

    // Create shop subscription (TRIAL status)
    const shopSubscription = await tx.shop_subscriptions.create({
      data: {
        shop_id: shopRecord.id,
        subscription_plan_id: defaultPlan.id,
        pricing_tier_id: pricingTier.id,
        status: "TRIAL",
        start_date: new Date(),
        is_active: true,
        auto_renew: true,
      },
    });

    // Create subscription trial
    const subscriptionTrial = await tx.subscription_trials.create({
      data: {
        shop_subscription_id: shopSubscription.id,
        threshold_amount: pricingTier.trial_threshold_amount,
        status: "ACTIVE",
        started_at: new Date(),
        // ❌ REMOVED: accumulated_revenue - always calculate from commission_records
        commission_saved: 0.0,
      },
    });

    console.log(`✅ Trial activated for ${shopDomain}:`);
    console.log(`   - Plan: ${defaultPlan.name}`);
    console.log(`   - Currency: ${shopRecord.currency_code}`);
    console.log(`   - Threshold: ${pricingTier.trial_threshold_amount}`);

    return {
      shop_subscription: shopSubscription,
      subscription_trial: subscriptionTrial,
    };
  }

  private async markOnboardingCompleted(shopDomain: string, tx: any) {
    await tx.shops.update({
      where: { shop_domain: shopDomain },
      data: { onboarding_completed: true },
    });
  }

  private async activateWebPixel(admin: any, shopDomain: string) {
    try {
      const backendUrl = process.env.BACKEND_URL;
      const webPixelSettings = {
        backend_url: backendUrl,
      };

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
        console.log("✅ Atlas web pixel created successfully");
        return createResponseJson.data.webPixelCreate.webPixel;
      }

      // If creation failed due to "TAKEN" error, the pixel already exists
      const hasTakenError =
        createResponseJson.data?.webPixelCreate?.userErrors?.some(
          (error: any) => error.code === "TAKEN",
        );

      if (hasTakenError) {
        console.log("✅ Web pixel already exists and is active");
        return { id: "existing", settings: webPixelSettings };
      }

      // Log other creation errors but don't fail the entire flow
      const errors = createResponseJson.data?.webPixelCreate?.userErrors || [];
      if (errors.length > 0) {
        console.warn("⚠️ Web pixel creation had issues:", errors);
      }

      console.log("ℹ️ Web pixel activation completed with warnings");
      return null;
    } catch (error) {
      console.error("❌ Failed to activate Atlas web pixel:", error);
      // Don't throw the error to prevent breaking the entire afterAuth flow
      return null;
    }
  }

  private async triggerAnalysis(shopDomain: string) {
    try {
      // Get shop information from database to retrieve shop_id and access_token
      const shop = await prisma.shops.findUnique({
        where: { shop_domain: shopDomain },
        select: { id: true, access_token: true },
      });

      if (!shop) {
        throw new Error(`Shop not found for domain: ${shopDomain}`);
      }

      if (!shop.access_token) {
        throw new Error(`No access token found for shop: ${shopDomain}`);
      }

      // Create a job ID; Kafka ensures ordering and we key by shop for partitioning
      const jobId = `analysis_${shopDomain}_${Date.now()}`;

      // Create collection payload for full analysis (all data types)
      const collectionPayload = {
        data_types: ["products", "orders", "customers", "collections"],
      };

      const jobData = {
        event_type: "data_collection",
        job_id: jobId,
        shop_id: shop.id,
        job_type: "data_collection",
        mode: "historical", // This ensures all historical data is processed during onboarding
        collection_payload: collectionPayload, // New: specify what data to collect
        trigger_source: "analysis", // New: indicate this is triggered by analysis
        timestamp: new Date().toISOString(),
      };

      const producer = await KafkaProducerService.getInstance();
      const messageId = await producer.publishDataJobEvent(jobData);
      console.log(`✅ Data collection job published to Kafka: ${messageId}`);
      return { success: true, messageId };
    } catch (error: any) {
      console.error("❌ Failed to publish data collection job:", error);
      throw new Error(`Failed to trigger analysis: ${error.message}`);
    }
  }
}
