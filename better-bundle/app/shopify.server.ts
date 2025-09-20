import "@shopify/shopify-app-remix/adapters/node";
import {
  ApiVersion,
  AppDistribution,
  shopifyApp,
} from "@shopify/shopify-app-remix/server";
import { PrismaSessionStorage } from "@shopify/shopify-app-session-storage-prisma";
import prisma from "./db.server";
import { activateAtlasWebPixel } from "./services/atlas.service";

const shopify = shopifyApp({
  apiKey: process.env.SHOPIFY_API_KEY,
  apiSecretKey: process.env.SHOPIFY_API_SECRET || "",
  apiVersion: ApiVersion.January25,
  scopes: process.env.SCOPES?.split(","),
  appUrl: process.env.SHOPIFY_APP_URL || "",
  authPathPrefix: "/auth",
  sessionStorage: new PrismaSessionStorage(prisma),
  distribution: AppDistribution.AppStore,
  hooks: {
    afterAuth: async ({ session, admin }) => {
      console.log("🔐 afterAuth hook triggered for shop:", session.shop);
      const myshopifyDomain = session.shop;
      try {
        // Fetch shop details including custom domain from Shopify API
        console.log("🔍 Fetching shop details from Shopify API");
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

        // Extract custom domain (primary domain if different from myshopify domain)
        const customDomain =
          shop.primaryDomain?.host !== shop.myshopifyDomain
            ? shop.primaryDomain?.host
            : null;

        await prisma.shop.upsert({
          where: { shopDomain: myshopifyDomain },
          update: {
            isActive: true,
            accessToken: (session as any).accessToken ?? "",
            customDomain: customDomain,
            email: shop.email,
            currencyCode: shop.currencyCode,
            planType: shop.plan?.displayName || "Free",
          },
          create: {
            shopDomain: myshopifyDomain,
            accessToken: (session as any).accessToken ?? "",
            isActive: true,
            customDomain: customDomain,
            email: shop.email,
            currencyCode: shop.currencyCode,
            planType: shop.plan?.displayName || "Free",
          },
        });

        console.log(
          "⚙️ Widget configuration no longer needed - using Shopify native approach",
        );

        // Create usage-based subscription for new installations
        console.log("💰 Checking for existing billing plan...");
        const existingBillingPlan = await prisma.billingPlan.findFirst({
          where: {
            shopId: myshopifyDomain,
            status: "active",
          },
        });

        if (!existingBillingPlan) {
          console.log(
            "🎉 Creating usage-based subscription for new installation",
          );

          // Get shop record to get the ID
          const shopRecord = await prisma.shop.findUnique({
            where: { shopDomain: myshopifyDomain },
            select: { id: true, currencyCode: true },
          });

          if (shopRecord) {
            // Create usage-based billing plan (subscription will be created via API)
            const billingPlan = await prisma.billingPlan.create({
              data: {
                shopId: shopRecord.id,
                shopDomain: myshopifyDomain,
                name: "Usage-Based Trial Plan",
                type: "usage_based",
                status: "active",
                configuration: {
                  usage_based: true,
                  trial_active: true,
                  trial_threshold: 200.0,
                  trial_revenue: 0.0,
                  revenue_share_rate: 0.03,
                  capped_amount: 1000.0,
                  currency: shopRecord.currencyCode || "USD",
                  subscription_pending: true,
                },
                effectiveFrom: new Date(),
                isTrialActive: true,
                trialThreshold: 200.0,
                trialRevenue: 0.0,
              },
            });

            console.log(
              `✅ Usage-based billing plan created: ${billingPlan.id}`,
            );
            console.log("📋 Subscription will be created via API call");
          } else {
            console.log(
              "⚠️ Shop record not found, skipping billing plan creation",
            );
          }
        } else {
          console.log("✅ Billing plan already exists, skipping creation");
        }

        // Activate Atlas web pixel extension
        console.log("🎯 Activating Atlas web pixel for:", myshopifyDomain);
        await activateAtlasWebPixel(admin, myshopifyDomain);

        console.log("✅ afterAuth provisioning completed successfully");
      } catch (err) {
        console.error("❌ afterAuth provisioning error", err);
      }
    },
  },
  future: {
    unstable_newEmbeddedAuthStrategy: true,
    removeRest: true,
  },
  ...(process.env.SHOP_CUSTOM_DOMAIN
    ? { customShopDomains: [process.env.SHOP_CUSTOM_DOMAIN] }
    : {}),
});

export default shopify;
export const apiVersion = ApiVersion.January25;
export const addDocumentResponseHeaders = shopify.addDocumentResponseHeaders;
export const authenticate = shopify.authenticate;
export const unauthenticated = shopify.unauthenticated;
export const login = shopify.login;
export const registerWebhooks = shopify.registerWebhooks;
export const sessionStorage = shopify.sessionStorage;
