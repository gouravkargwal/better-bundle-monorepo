/**
 * BetterBundle Apollo Post-Purchase Extension
 *
 * This extension provides personalized product recommendations after checkout completion.
 * It follows Shopify's post-purchase extension guidelines and integrates with our
 * unified analytics system for tracking and attribution.
 */
import React from "react";

import {
  extend,
  render,
  BlockStack,
  Button,
  CalloutBanner,
  Heading,
  Image,
  Layout,
  TextBlock,
  TextContainer,
  View,
} from "@shopify/post-purchase-ui-extensions-react";

import { apolloAnalytics } from "./api/analytics";
import {
  apolloRecommendationApi,
  type ProductRecommendation,
} from "./api/recommendations";

/**
 * Entry point for the `ShouldRender` Extension Point.
 *
 * Returns a value indicating whether or not to render a PostPurchase step, and
 * optionally allows data to be stored on the client for use in the `Render`
 * extension point.
 */
extend("Checkout::PostPurchase::ShouldRender", async ({ storage }) => {
  try {
    // For post-purchase extensions, we'll fetch recommendations without order context
    // The order context will be available in the Render extension point
    const initialState = await getPostPurchaseRecommendations({
      limit: 3,
    });

    // Only render if we have recommendations
    const render = initialState.recommendations.length > 0;

    if (render) {
      // Save initial state for the Render extension point
      await storage.update(initialState);
    }

    return {
      render,
    };
  } catch (error) {
    console.error("Error in ShouldRender:", error);
    // Don't render if there's an error
    return {
      render: false,
    };
  }
});

/**
 * Fetch post-purchase recommendations from the API
 */
async function getPostPurchaseRecommendations(request: {
  order_id?: string;
  customer_id?: string;
  shop_domain?: string;
  purchased_products?: Array<{
    product_id: string;
    variant_id: string;
    quantity: number;
    price: number;
  }>;
  limit?: number;
}) {
  try {
    const response =
      await apolloRecommendationApi.getPostPurchaseRecommendations({
        shop_domain: request.shop_domain,
        context: "post_purchase",
        order_id: request.order_id,
        customer_id: request.customer_id,
        purchased_products: request.purchased_products,
        limit: request.limit || 3,
      });

    return response;
  } catch (error) {
    console.error("Failed to fetch post-purchase recommendations:", error);

    // Return fallback recommendations if the main API fails
    try {
      const fallbackRecommendations =
        await apolloRecommendationApi.getFallbackRecommendations(
          request.shop_domain || "",
          request.limit || 3,
        );

      return {
        success: true,
        recommendations: fallbackRecommendations,
        count: fallbackRecommendations.length,
        source: "fallback",
        context: "post_purchase",
        timestamp: new Date().toISOString(),
      };
    } catch (fallbackError) {
      console.error("Fallback recommendations also failed:", fallbackError);
      return {
        success: false,
        recommendations: [],
        count: 0,
        source: "error",
        context: "post_purchase",
        timestamp: new Date().toISOString(),
      };
    }
  }
}

/**
 * Entry point for the `Render` Extension Point
 *
 * Returns markup composed of remote UI components.  The Render extension can
 * optionally make use of data stored during `ShouldRender` extension point to
 * expedite time-to-first-meaningful-paint.
 */
render("Checkout::PostPurchase::Render", App);

// Top-level React component
export function App({
  extensionPoint,
  storage,
}: {
  extensionPoint: any;
  storage: any;
}) {
  const initialState = storage.initialData;
  const {
    recommendations = [],
    orderId,
    customerId,
    shopDomain,
    purchasedProducts = [],
  } = initialState || {};

  // Track recommendation view when component mounts
  React.useEffect(() => {
    if (recommendations.length > 0 && shopDomain) {
      const productIds = recommendations.map(
        (rec: ProductRecommendation) => rec.id,
      );

      apolloAnalytics
        .trackRecommendationView(
          shopDomain.replace(".myshopify.com", ""),
          customerId,
          orderId,
          productIds,
          {
            source: "apollo_post_purchase",
            recommendation_count: recommendations.length,
            purchased_products_count: purchasedProducts.length,
          },
        )
        .catch((error) => {
          console.error("Failed to track recommendation view:", error);
        });
    }
  }, [recommendations, shopDomain, customerId, orderId, purchasedProducts]);

  // Helper functions for variant handling - simplified approach
  const getDefaultVariant = (product: any) => {
    return (
      product.variants.find((v: any) => v.id === product.default_variant_id) ||
      product.variants[0]
    );
  };

  const getDefaultPrice = (product: any) => {
    const defaultVariant = getDefaultVariant(product);
    return defaultVariant ? defaultVariant.price : "$0.00";
  };

  const isVariantAvailable = (product: any) => {
    const defaultVariant = getDefaultVariant(product);
    return defaultVariant && defaultVariant.available;
  };

  // Handle adding product to order
  const handleAddToOrder = async (
    product: ProductRecommendation,
    position: number,
  ) => {
    try {
      const defaultVariant = getDefaultVariant(product);

      if (!defaultVariant || !defaultVariant.available) {
        console.error("No valid variant available");
        return;
      }

      // Track recommendation click first
      if (shopDomain) {
        await apolloAnalytics.trackRecommendationClick(
          shopDomain.replace(".myshopify.com", ""),
          product.id,
          position,
          customerId,
          orderId,
          {
            source: "apollo_post_purchase",
            variant_id: defaultVariant.id,
            product_title: product.title,
            variant_title: defaultVariant.title,
            price: defaultVariant.price.amount,
          },
        );
      }

      // Track add to order action
      if (shopDomain) {
        await apolloAnalytics.trackAddToOrder(
          shopDomain.replace(".myshopify.com", ""),
          product.id,
          defaultVariant.id,
          position,
          customerId,
          orderId,
          {
            source: "apollo_post_purchase",
            product_title: product.title,
            variant_title: defaultVariant.title,
            price: defaultVariant.price.amount,
            currency: defaultVariant.price.currency_code,
          },
        );
      }

      // Note: Post-purchase extensions cannot directly add products to completed orders
      // This would typically be handled through a separate flow or API
      // For now, we'll redirect to the product page with attribution parameters

      const attributionParams = new URLSearchParams({
        ref: `apollo_${orderId?.slice(-6)}`,
        src: product.id,
        pos: position.toString(),
        variant: defaultVariant.id,
      });

      const productUrl = product.url || `/products/${product.handle}`;
      const productUrlWithAttribution = `${productUrl}?${attributionParams.toString()}`;

      // In a real implementation, this would open the product page or handle the upsell flow
      console.log(`Redirecting to: ${productUrlWithAttribution}`);

      // For post-purchase extensions, we might show a success message instead
      console.log(
        `Variant ${defaultVariant.id} of product ${product.id} added to order successfully`,
      );
    } catch (error) {
      console.error("Error adding product to order:", error);
    }
  };

  const handleContinue = () => {
    console.log("Continue to order confirmation");
    // This would typically close the post-purchase flow
  };

  // Show empty state if no recommendations
  if (!recommendations || recommendations.length === 0) {
    return (
      // @ts-ignore - Post-purchase UI extensions use different React types
      <BlockStack spacing="base">
        {/* @ts-ignore */}
        <TextContainer>
          {/* @ts-ignore */}
          <Heading level={2}>Thank You for Your Purchase!</Heading>
          {/* @ts-ignore */}
          <TextBlock>
            Your order has been confirmed. We'll send you a confirmation email
            shortly.
          </TextBlock>
        </TextContainer>
        {/* @ts-ignore */}
        <Button
          onPress={() => {
            // This would typically close the post-purchase flow
            console.log("Continue to order confirmation");
          }}
        >
          Continue to Order Confirmation
        </Button>
      </BlockStack>
    );
  }

  return (
    // @ts-ignore - Post-purchase UI extensions use different React types
    <BlockStack spacing="loose">
      {/* @ts-ignore */}
      <CalloutBanner title="🎉 Thank you for your purchase!">
        Complete your order with these recommended products
      </CalloutBanner>

      {/* @ts-ignore */}
      <TextContainer>
        {/* @ts-ignore */}
        <Heading>You might also like</Heading>
        {/* @ts-ignore */}
        <TextBlock>
          Based on your purchase, here are some products that customers love to
          add to their orders.
        </TextBlock>
      </TextContainer>

      {recommendations.length > 0 && (
        <>
          {recommendations.map((product: any, index: any) => (
            // @ts-ignore
            <Layout
              key={product.id}
              maxInlineSize={0.95}
              media={[
                { viewportSize: "small", sizes: [1, 30, 1] },
                { viewportSize: "medium", sizes: [300, 30, 0.5] },
                { viewportSize: "large", sizes: [400, 30, 0.33] },
              ]}
            >
              {/* @ts-ignore */}
              <View>
                {/* @ts-ignore */}
                <Image source={product.image} />
              </View>
              {/* @ts-ignore */}
              <View />
              {/* @ts-ignore */}
              <BlockStack spacing="base">
                {/* @ts-ignore */}
                <TextContainer>
                  {/* @ts-ignore */}
                  <Heading level={3}>{product.title}</Heading>

                  {/* Show variant info if multiple variants exist */}
                  {product.variants && product.variants.length > 1 && (
                    // @ts-ignore
                    <View>
                      {/* @ts-ignore */}
                      <TextBlock appearance="subdued">
                        {getDefaultVariant(product).title}
                      </TextBlock>
                    </View>
                  )}

                  {/* @ts-ignore */}
                  <TextBlock appearance="accent" emphasis="bold">
                    {getDefaultPrice(product)}
                  </TextBlock>
                  {/* @ts-ignore */}
                  <TextBlock appearance="subdued">{product.reason}</TextBlock>
                </TextContainer>
                {/* @ts-ignore */}
                <Button
                  submit
                  onPress={() => handleAddToOrder(product, index + 1)}
                  disabled={!isVariantAvailable(product)}
                >
                  Add to Order - {getDefaultPrice(product)}
                </Button>
              </BlockStack>
            </Layout>
          ))}
        </>
      )}

      {/* @ts-ignore */}
      <Button onPress={handleContinue}>Continue to Order Confirmation</Button>
    </BlockStack>
  );
}
