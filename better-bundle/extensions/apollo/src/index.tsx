import { extend, render } from "@shopify/post-purchase-ui-extensions-react";

import { getSessionAndRecommendations } from "./api/recommendations";
import { initializeJWTStorage, getStoredTokenSync } from "./utils/jwt";
import App from "./App";

extend(
  "Checkout::PostPurchase::ShouldRender",
  async ({ inputData, storage }) => {
    try {
      // Initialize JWT storage for token persistence
      initializeJWTStorage(storage);

      const { initialPurchase, shop, locale } = inputData;

      const shopDomain = shop.domain;
      const customerId = initialPurchase.customerId
        ? String(initialPurchase.customerId)
        : undefined; // ✅ Ensure string
      const orderId = String(initialPurchase.referenceId); // ✅ Ensure string

      const purchasedProducts = initialPurchase.lineItems.map((item: any) => ({
        id: item.product.id.toString(),
        title: item.product.title,
        variant: item.product.variant,
        quantity: item.quantity,
        totalPrice: item.totalPriceSet,
      }));

      // Call your API that returns the exact structure from your example
      const result = await getSessionAndRecommendations(
        shopDomain,
        customerId,
        orderId,
        purchasedProducts.map((p: any) => p.id),
        3,
        {
          source: "apollo_post_purchase",
          locale,
          shopId: shop.id,
          totalPrice: initialPurchase.totalPriceSet,
          lineItemCount: initialPurchase.lineItems.length,
        },
      );

      const shouldRender = result.success && result.recommendations?.length > 0;

      if (shouldRender) {
        // Validate session data exists
        if (!result.sessionId) {
          console.error("Apollo: No session ID in API response");
          return { render: false };
        }

        // Get token from storage (it was stored during the API call)
        const tokenData = getStoredTokenSync();

        // Store recommendations and token together (same storage update)
        await storage.update({
          recommendations: result.recommendations,
          sessionId: result.sessionId,
          orderId,
          customerId,
          shopDomain,
          purchasedProducts,
          source: "apollo_combined_api",
          timestamp: Date.now(),
          shop,
          locale,
          initialPurchase: {
            referenceId: initialPurchase.referenceId,
            totalPriceSet: initialPurchase.totalPriceSet,
            lineItems: initialPurchase.lineItems,
          },
          // Include token so it's available in App component's storage.initialData
          ...(tokenData && {
            bb_jwt_access_token: tokenData.token,
            bb_jwt_token_expiry: tokenData.expiresIn,
            bb_jwt_shop_domain: tokenData.shopDomain,
            ...(tokenData.refreshToken && {
              bb_jwt_refresh_token: tokenData.refreshToken,
            }),
          }),
        });
      }

      return { render: shouldRender };
    } catch (error) {
      console.error("Apollo ShouldRender error:", error);
      return { render: false };
    }
  },
);

render("Checkout::PostPurchase::Render", (props) => <App {...props} />);
