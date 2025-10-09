import { extend, render } from "@shopify/post-purchase-ui-extensions-react";

import { apolloRecommendationApi } from "./api/recommendations";
import App from "./App";

extend(
  "Checkout::PostPurchase::ShouldRender",
  async ({ inputData, storage }) => {
    try {
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

      console.log(
        `Apollo ShouldRender - Shop: ${shopDomain}, Order: ${orderId}`,
      );

      // Call your API that returns the exact structure from your example
      const result = await apolloRecommendationApi.getSessionAndRecommendations(
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

      console.log(
        `Apollo ShouldRender: ${shouldRender}, Recommendations: ${result.recommendations?.length || 0}`,
      );

      if (shouldRender) {
        // Validate session data exists
        if (!result.sessionId) {
          console.error("Apollo: No session ID in API response");
          return { render: false };
        }

        // Store the API response data directly
        await storage.update({
          recommendations: result.recommendations, // Your API structure
          sessionId: result.sessionId, // ✅ From our fixed API client
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
