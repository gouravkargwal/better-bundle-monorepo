import "@shopify/shopify-app-remix/adapters/node";
import {
  ApiVersion,
  AppDistribution,
  shopifyApp,
} from "@shopify/shopify-app-remix/server";
import { PrismaSessionStorage } from "@shopify/shopify-app-session-storage-prisma";
import prisma from "./db.server";

const shopify = shopifyApp({
  apiKey: process.env.SHOPIFY_API_KEY,
  apiSecretKey: process.env.SHOPIFY_API_SECRET || "",
  apiVersion: ApiVersion.October25,
  scopes: process.env.SCOPES?.split(","),
  appUrl: process.env.SHOPIFY_APP_URL || "",
  isEmbeddedApp: true,
  authPathPrefix: "/auth",
  sessionStorage: new PrismaSessionStorage(prisma, { tableName: "sessions" }),
  distribution: AppDistribution.AppStore,
  future: {
    // Auth code flow, not token exchange. Left off deliberately: switching it
    // on changes how every install obtains its token, which is not something to
    // fold into an unrelated change.
    unstable_newEmbeddedAuthStrategy: false,
    // `removeRest` was dropped here: v4 deleted REST support outright, so the
    // flag no longer exists and the type rejects it. Nothing to migrate — this
    // app was already GraphQL-only.
  },
  ...(process.env.SHOP_CUSTOM_DOMAIN
    ? { customShopDomains: [process.env.SHOP_CUSTOM_DOMAIN] }
    : {}),
});

export default shopify;
export const addDocumentResponseHeaders = shopify.addDocumentResponseHeaders;
export const authenticate = shopify.authenticate;
export const login = shopify.login;
