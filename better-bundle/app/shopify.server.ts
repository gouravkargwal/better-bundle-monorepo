import "@shopify/shopify-app-remix/adapters/node";
import {
  ApiVersion,
  AppDistribution,
  shopifyApp,
} from "@shopify/shopify-app-remix/server";
import { PrismaSessionStorage } from "@shopify/shopify-app-session-storage-prisma";
import prisma from "./db.server";
// Widget configuration removed - using Shopify native approach

/**
 * Activates the Atlas web pixel extension for the shop
 */
async function activateAtlasWebPixel(admin: any, shopDomain: string) {
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

        console.log("📝 Creating/updating shop record for:", myshopifyDomain);
        console.log("🌐 Custom domain:", customDomain || "Not set");

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
