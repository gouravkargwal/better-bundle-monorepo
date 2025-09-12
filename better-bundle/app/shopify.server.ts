import "@shopify/shopify-app-remix/adapters/node";
import {
  ApiVersion,
  AppDistribution,
  shopifyApp,
} from "@shopify/shopify-app-remix/server";
import { PrismaSessionStorage } from "@shopify/shopify-app-session-storage-prisma";
import prisma from "./db.server";
import { createDefaultConfiguration } from "./services/widget-config.service";
import { AnalysisPipelineService } from "./services/analysis-pipeline.service";

/**
 * Activates the Atlas web pixel extension for the shop
 */
async function activateAtlasWebPixel(admin: any, shopDomain: string) {
  try {
    // Get the backend URL from environment or use a default
    const backendUrl =
      process.env.SHOPIFY_APP_URL ||
      "https://namibia-nokia-internet-secretariat.trycloudflare.com";

    const webPixelSettings = {
      backend_url: backendUrl,
      shop_domain: shopDomain,
    };

    const mutation = `
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

    const response = await admin.graphql(mutation, {
      variables: {
        webPixel: {
          settings: JSON.stringify(webPixelSettings),
        },
      },
    });

    const responseJson = await response.json();

    if (responseJson.data?.webPixelCreate?.userErrors?.length > 0) {
      console.error(
        "❌ Web pixel creation errors:",
        responseJson.data.webPixelCreate.userErrors,
      );
      throw new Error(
        `Web pixel creation failed: ${responseJson.data.webPixelCreate.userErrors.map((e: any) => e.message).join(", ")}`,
      );
    }

    if (responseJson.data?.webPixelCreate?.webPixel) {
      console.log(
        "✅ Atlas web pixel activated successfully:",
        responseJson.data.webPixelCreate.webPixel.id,
      );
      return responseJson.data.webPixelCreate.webPixel;
    } else {
      throw new Error("No web pixel returned from mutation");
    }
  } catch (error) {
    console.error("❌ Failed to activate Atlas web pixel:", error);
    // Don't throw the error to prevent breaking the entire afterAuth flow
    // The app can still function without the web pixel
  }
}

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
        console.log("📝 Creating/updating shop record for:", myshopifyDomain);
        await prisma.shop.upsert({
          where: { shopDomain: myshopifyDomain },
          update: {
            isActive: true,
            accessToken: (session as any).accessToken ?? "",
          },
          create: {
            shopDomain: myshopifyDomain,
            accessToken: (session as any).accessToken ?? "",
            isActive: true,
          },
        });

        console.log(
          "⚙️ Creating default widget configuration for:",
          myshopifyDomain,
        );
        await createDefaultConfiguration(myshopifyDomain);

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
