import { shopifyApp, AppDistribution } from "@shopify/shopify-app-remix/server";
import { LATEST_API_VERSION } from "@shopify/shopify-api";
import { prisma } from "./core/database/prisma.server";
import { PrismaSessionStorage } from "@shopify/shopify-app-session-storage-prisma";

// Hardcoded scopes to ensure they're always correct
const scopes = [
  "write_products",
  "read_products",
  "read_orders",
  "write_orders",
];

const shopify = shopifyApp({
  apiKey: process.env.SHOPIFY_API_KEY || "87c44f5966daa80691a480bcd03c225c",
  apiSecretKey: process.env.SHOPIFY_API_SECRET || "your_api_secret_here",
  apiVersion: LATEST_API_VERSION,
  scopes: scopes,
  appUrl: process.env.SHOPIFY_APP_URL || "https://betterbundle.vercel.app",
  authPathPrefix: "/auth",
  sessionStorage: new PrismaSessionStorage(prisma),
  distribution: AppDistribution.AppStore,
  isEmbeddedApp: true,
  useOnlineTokens: false,
  future: {
    unstable_newEmbeddedAuthStrategy: true,
    removeRest: true,
  },
});

export default shopify;
export const apiVersion = LATEST_API_VERSION;
export const addDocumentResponseHeaders = shopify.addDocumentResponseHeaders;
export const authenticate = shopify.authenticate;
export const unauthenticated = shopify.unauthenticated;
export const login = shopify.login;
export const registerWebhooks = shopify.registerWebhooks;
export const sessionStorage = shopify.sessionStorage;
