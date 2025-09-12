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
  const initialState = await getRenderData();
  const render = true;

  if (render) {
    // Saves initial state, provided to `Render` via `storage.initialData`
    await storage.update(initialState);
  }

  return {
    render,
  };
});

// Simulate results of network call, etc.
async function getRenderData() {
  return {
    recommendations: [
      {
        id: "gid://shopify/Product/1234567890",
        title: "Perfect Addition to Your Order",
        handle: "perfect-addition",
        image:
          "https://cdn.shopify.com/static/images/examples/img-placeholder-1120x1120.png",
        price: "₹299",
        currency: "INR",
        variantId: "gid://shopify/ProductVariant/1234567890",
        reason: "Customers who bought this also loved",
      },
      {
        id: "gid://shopify/Product/1234567891",
        title: "Complete Your Look",
        handle: "complete-look",
        image:
          "https://cdn.shopify.com/static/images/examples/img-placeholder-1120x1120.png",
        price: "₹499",
        currency: "INR",
        variantId: "gid://shopify/ProductVariant/1234567891",
        reason: "Frequently bought together",
      },
    ],
  };
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
  const recommendations = initialState?.recommendations || [];

  return (
    <BlockStack spacing="loose">
      <CalloutBanner title="🎉 Thank you for your purchase!">
        Complete your order with these recommended products
      </CalloutBanner>

      <TextContainer>
        <Heading>You might also like</Heading>
        <TextBlock>
          Based on your purchase, here are some products that customers love to
          add to their orders.
        </TextBlock>
      </TextContainer>

      {recommendations.map((product, index) => (
        <Layout
          key={product.id}
          maxInlineSize={0.95}
          media={[
            { viewportSize: "small", sizes: [1, 30, 1] },
            { viewportSize: "medium", sizes: [300, 30, 0.5] },
            { viewportSize: "large", sizes: [400, 30, 0.33] },
          ]}
        >
          <View>
            <Image source={product.image} />
          </View>
          <View />
          <BlockStack spacing="base">
            <TextContainer>
              <Heading level={3}>{product.title}</Heading>
              <TextBlock appearance="accent" emphasis="bold">
                {product.price}
              </TextBlock>
              <TextBlock appearance="subdued">{product.reason}</TextBlock>
            </TextContainer>
            <Button
              submit
              onPress={() => {
                console.log(`Adding product ${product.id} to order`);
                // Here you would typically add the product to the order
              }}
            >
              Add to Order - {product.price}
            </Button>
          </BlockStack>
        </Layout>
      ))}

      <Button
        onPress={() => {
          console.log("Continue to order confirmation");
          // This would typically close the post-purchase flow
        }}
      >
        Continue to Order Confirmation
      </Button>
    </BlockStack>
  );
}
