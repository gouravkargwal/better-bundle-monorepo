import prisma from "../../../db.server";
import { getCurrencySymbol } from "../../../utils/currency";
import { KafkaProducerService } from "../../../services/kafka/kafka-producer.service";
import logger from "app/utils/logger";

export class OnboardingService {
  async getOnboardingData(shopDomain: string, admin: any) {
    try {
      // Get shop info from Shopify
      const shopData = await this.getShopInfoFromShopify(admin);

      // Get subscription plan configuration
      const subscriptionPlan = await this.getSubscriptionPlanConfig(
        shopDomain,
        shopData.currencyCode,
      );

      return {
        subscriptionPlan,
      };
    } catch (error) {
      logger.error({ err: error }, "Error getting onboarding data");
      throw new Error("Failed to get onboarding data");
    }
  }

  async completeOnboarding(session: any, admin: any) {
    try {
      // Get shop data from Shopify
      const shopData = await this.getShopInfoFromShopify(admin);

      // Complete onboarding in transaction (without marking complete)
      const shop = await this.completeOnboardingTransaction(session, shopData);

      // Activate web pixel
      await this.activateWebPixel(admin, session.shop);

      // Trigger analysis using shop record from transaction (avoids extra DB query)
      await this.triggerAnalysis(session.shop, shop.id, session.accessToken);

      // Mark onboarding completed AFTER Kafka succeeds
      await this.markOnboardingCompleted(session.shop);
    } catch (error) {
      logger.error({ error }, "Error completing onboarding");
      throw new Error("Failed to complete onboarding");
    }
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
              shopifyPlus
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
      logger.error({ error }, "Error getting shop info from Shopify");
      throw new Error("Failed to fetch shop data from Shopify API");
    }
  }

  private async getSubscriptionPlanConfig(
    shopDomain: string,
    currencyCode: string,
  ) {
    try {
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

      return {
        symbol: getCurrencySymbol(currencyCode),
        monthly_fee: Number(defaultPlan.monthly_fee) || 29,
        trial_days: Number(defaultPlan.trial_days) || 14,
        plan_name: defaultPlan.name || "Pro",
      };
    } catch (error) {
      logger.error({ error }, "Error getting subscription plan configuration");
      throw new Error("Failed to get subscription plan configuration");
    }
  }

  private async completeOnboardingTransaction(session: any, shopData: any) {
    return await prisma.$transaction(async (tx) => {
      try {
        // Create or update shop
        const shop = await this.createOrUpdateShop(session, shopData, tx);

        // Activate trial billing plan
        await this.activateTrialBillingPlan(session.shop, shop, tx);

        return shop;
      } catch (error) {
        logger.error({ error }, "Error completing onboarding transaction");
        throw new Error("Failed to complete onboarding transaction");
      }
    });
  }

  private async createOrUpdateShop(session: any, shopData: any, tx: any) {
    try {
      // Check if this is a reinstall
      const existingShop = await tx.shops.findUnique({
        where: { shop_domain: shopData.myshopifyDomain },
      });

      const isReinstall = existingShop && !existingShop.is_active;

      return await tx.shops.upsert({
        where: { shop_domain: shopData.myshopifyDomain },
        update: {
          access_token: session.accessToken,
          currency_code: shopData.currencyCode,
          email: shopData.email,
          // @deprecated shops.plan_type — to be removed in Phase 4. Use shop_subscriptions.subscription_plan.plan_type for billing plan type.
          plan_type: shopData.plan.displayName,
          is_active: true,
          shopify_plus: shopData.plan.shopifyPlus || false,
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
          // @deprecated shops.plan_type — to be removed in Phase 4. Use shop_subscriptions.subscription_plan.plan_type for billing plan type.
          plan_type: shopData.plan.displayName,
          is_active: true,
          onboarding_completed: false,
          shopify_plus: shopData.plan.shopifyPlus || false,
        },
      });
    } catch (error) {
      logger.error({ error }, "Error creating or updating shop");
      throw new Error("Failed to create or update shop");
    }
  }

  private async activateTrialBillingPlan(
    shopDomain: string,
    shopRecord: any,
    tx: any,
  ) {
    try {
      // Idempotency: do not create another subscription if one already exists
      const existing = await tx.shop_subscriptions.findFirst({
        where: {
          shop_id: shopRecord.id,
          OR: [
            { is_active: true },
            {
              status: {
                in: ["TRIAL", "PENDING_APPROVAL", "ACTIVE", "SUSPENDED"] as any,
              },
            },
          ],
        },
        orderBy: { created_at: "desc" },
      });

      if (existing) {
        return existing;
      }

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

      // Create shop subscription (TRIAL status) with flat fee trial configuration
      const trialDays = Number(defaultPlan.trial_days) || 14;
      const shopSubscription = await tx.shop_subscriptions.create({
        data: {
          shop_id: shopRecord.id,
          subscription_plan_id: defaultPlan.id,
          subscription_type: "TRIAL",
          status: "TRIAL",
          started_at: new Date(),
          is_active: true,
          auto_renew: true,
          trial_duration_days: trialDays,
        },
      });

      return shopSubscription;
    } catch (error: any) {
      logger.error(
        {
          err: {
            name: error?.name,
            code: error?.code,
            message: error?.message,
            meta: error?.meta,
          },
        },
        "Error activating trial billing plan",
      );
      throw new Error("Failed to activate trial billing plan");
    }
  }

  private async markOnboardingCompleted(shopDomain: string) {
    try {
      await prisma.shops.update({
        where: { shop_domain: shopDomain },
        data: { onboarding_completed: true },
      });
    } catch (error) {
      logger.error({ error }, "Error marking onboarding completed");
      throw new Error("Failed to mark onboarding completed");
    }
  }

  private async activateWebPixel(admin: any, shopDomain: string) {
    try {
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
        return { id: "existing" };
      }

      // Log other creation errors but don't fail the entire flow
      const errors = createResponseJson.data?.webPixelCreate?.userErrors || [];
      if (errors.length > 0) {
        logger.warn({ errors }, "Web pixel creation had issues");
      }

      return null;
    } catch (error) {
      logger.error({ error }, "Failed to activate Atlas web pixel");
      // Don't throw the error to prevent breaking the entire afterAuth flow
      return null;
    }
  }

  private async triggerAnalysis(
    shopDomain: string,
    shopId: string,
    accessToken: string,
  ) {
    try {
      if (!accessToken) {
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
        shop_id: shopId,
        job_type: "data_collection",
        mode: "historical", // This ensures all historical data is processed during onboarding
        collection_payload: collectionPayload, // New: specify what data to collect
        trigger_source: "analysis", // New: indicate this is triggered by analysis
        timestamp: new Date().toISOString(),
      };

      const producer = await KafkaProducerService.getInstance();
      const messageId = await producer.publishDataJobEvent(jobData);
      return { success: true, messageId };
    } catch (error: any) {
      logger.error({ error }, "Failed to publish data collection job");
      throw new Error(`Failed to trigger analysis: ${error.message}`);
    }
  }
}
