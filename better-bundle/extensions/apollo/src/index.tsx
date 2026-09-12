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

      // Fast-path: If Shopify re-ran ShouldRender (e.g. because the customer changed their shipping region),
      // we check persistent storage. If we already fetched recommendations for this exact order ID,
      // skip the network call and return immediately to prevent losing the impression to a race condition.
      const cachedData = storage.initialData as any;
      if (
        cachedData?.orderId === orderId &&
        cachedData?.recommendations?.length > 0 &&
        Date.now() - (cachedData.timestamp || 0) < 1000 * 60 * 15 // Cache valid for 15 minutes
      ) {
        console.log("Apollo: Using persistent storage cache for ShouldRender");
        return { render: true };
      }

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
      } else {
         // Even if the backend returned no recommendations, cache that fact so we don't
         // hammer the backend if Shopify reruns ShouldRender for this order.
         await storage.update({
           orderId,
           timestamp: Date.now(),
           recommendations: [],
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
