import "@shopify/shopify-app-remix/adapters/node";
import {
  ApiVersion,
  AppDistribution,
  shopifyApp,
} from "@shopify/shopify-app-remix/server";
import { PrismaSessionStorage } from "@shopify/shopify-app-session-storage-prisma";
import prisma from "./db.server";
import { createDefaultConfiguration } from "./services/widget-config.service";

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
    afterAuth: async ({ session }) => {
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
