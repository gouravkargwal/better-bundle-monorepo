/**
 * Extend Shopify Checkout with a custom Post Purchase user experience.
 * This template provides two extension points:
 *
 *  1. ShouldRender - Called first, during the checkout process, when the
 *     payment page loads.
 *  2. Render - If requested by `ShouldRender`, will be rendered after checkout
 *     completes
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

/**
 * Entry point for the `ShouldRender` Extension Point.
 *
 * Returns a value indicating whether or not to render a PostPurchase step, and
 * optionally allows data to be stored on the client for use in the `Render`
 * extension point.
 */
extend("Checkout::PostPurchase::ShouldRender", async ({ storage }) => {
  // For now, we'll fetch recommendations without order/customer context
  // In a real implementation, you might get this from the extension context
  const initialState = await getRenderData();
  const render = initialState.recommendations.length > 0;

  if (render) {
    // Saves initial state, provided to `Render` via `storage.initialData`
    await storage.update(initialState);
  }

  return {
    render,
  };
});

// Fetch real recommendations from our API
async function getRenderData() {
  try {
    const response = await fetch("/api/v1/recommendations", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        context: "post_purchase",
        limit: 3,
        // We'll get order/customer info in the Render phase
      }),
    });

    if (!response.ok) {
      throw new Error(
        `Failed to fetch recommendations: ${response.statusText}`,
      );
    }

    const data = await response.json();
    return {
      recommendations: data.recommendations || [],
    };
  } catch (error) {
    console.error("Error fetching recommendations:", error);
    // Return empty recommendations on error
    return {
      recommendations: [],
    };
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
  const { recommendations = [] } = initialState || {};

  // Get order and customer information from the extension point
  const orderId = extensionPoint?.order?.id;
  const customerId = extensionPoint?.order?.customer?.id;
  const shopDomain = extensionPoint?.shop?.domain;

  // Handle adding product to order
  const handleAddToOrder = async (product: any) => {
    try {
      // Use the extensionPoint API to add the product to the order
      await extensionPoint.applyAttributeChange({
        type: "updateAttribute",
        key: `recommendation_${product.id}`,
        value: product.id,
      });

      // Track analytics
      try {
        await fetch("/api/v1/analytics", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            event: "recommendation_click",
            context: "post_purchase",
            productId: product.id,
            customerId,
            shopDomain,
            orderId,
            timestamp: new Date().toISOString(),
          }),
        });
      } catch (analyticsError) {
        console.error("Analytics tracking failed:", analyticsError);
        // Don't fail the main flow if analytics fails
      }

      console.log(`Product ${product.id} added to order successfully`);
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
                  {/* @ts-ignore */}
                  <TextBlock appearance="accent" emphasis="bold">
                    {product.price}
                  </TextBlock>
                  {/* @ts-ignore */}
                  <TextBlock appearance="subdued">{product.reason}</TextBlock>
                </TextContainer>
                {/* @ts-ignore */}
                <Button submit onPress={() => handleAddToOrder(product)}>
                  Add to Order - {product.price}
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
