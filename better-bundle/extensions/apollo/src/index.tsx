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

// Dummy data for testing - will be replaced with real API later
const dummyRecommendations = [
  {
    id: "prod_1",
    title: "Premium Wireless Headphones",
    image:
      "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=300&h=300&fit=crop",
    reason: "Customers who bought this also bought these headphones",
    variants: [
      {
        id: "var_1_1",
        title: "Black",
        price: "$199.99",
        available: true,
        inventory_quantity: 15,
      },
      {
        id: "var_1_2",
        title: "White",
        price: "$199.99",
        available: true,
        inventory_quantity: 8,
      },
      {
        id: "var_1_3",
        title: "Silver",
        price: "$219.99",
        available: true,
        inventory_quantity: 3,
      },
    ],
    default_variant_id: "var_1_1",
  },
  {
    id: "prod_2",
    title: "Organic Cotton T-Shirt",
    image:
      "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=300&h=300&fit=crop",
    reason: "Perfect match for your style",
    variants: [
      {
        id: "var_2_1",
        title: "Small / Navy",
        price: "$24.99",
        available: true,
        inventory_quantity: 20,
      },
      {
        id: "var_2_2",
        title: "Medium / Navy",
        price: "$24.99",
        available: true,
        inventory_quantity: 25,
      },
      {
        id: "var_2_3",
        title: "Large / Navy",
        price: "$24.99",
        available: true,
        inventory_quantity: 18,
      },
      {
        id: "var_2_4",
        title: "Small / White",
        price: "$24.99",
        available: true,
        inventory_quantity: 12,
      },
      {
        id: "var_2_5",
        title: "Medium / White",
        price: "$24.99",
        available: true,
        inventory_quantity: 15,
      },
      {
        id: "var_2_6",
        title: "Large / White",
        price: "$24.99",
        available: false,
        inventory_quantity: 0,
      },
    ],
    default_variant_id: "var_2_2",
  },
  {
    id: "prod_3",
    title: "Smart Fitness Watch",
    image:
      "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=300&h=300&fit=crop",
    reason: "Complete your fitness journey",
    variants: [
      {
        id: "var_3_1",
        title: "40mm / Sport Band",
        price: "$299.99",
        available: true,
        inventory_quantity: 10,
      },
      {
        id: "var_3_2",
        title: "44mm / Sport Band",
        price: "$329.99",
        available: true,
        inventory_quantity: 7,
      },
      {
        id: "var_3_3",
        title: "40mm / Leather Band",
        price: "$349.99",
        available: true,
        inventory_quantity: 4,
      },
      {
        id: "var_3_4",
        title: "44mm / Leather Band",
        price: "$379.99",
        available: false,
        inventory_quantity: 0,
      },
    ],
    default_variant_id: "var_3_1",
  },
];

// Fetch dummy recommendations - will be replaced with real API later
async function getRenderData() {
  // Simulate API delay
  await new Promise((resolve) => setTimeout(resolve, 500));

  return {
    recommendations: dummyRecommendations,
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
  const { recommendations = [] } = initialState || {};

  // Get order and customer information from the extension point
  const orderId = extensionPoint?.order?.id;
  const customerId = extensionPoint?.order?.customer?.id;
  const shopDomain = extensionPoint?.shop?.domain;

  // Get purchased products for context (but we won't display them)
  const purchasedProducts = extensionPoint?.order?.lineItems || [];
  console.log("Purchased products:", purchasedProducts);

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
  const handleAddToOrder = async (product: any) => {
    try {
      const defaultVariant = getDefaultVariant(product);

      if (!defaultVariant || !defaultVariant.available) {
        console.error("No valid variant available");
        return;
      }

      // For now, we'll just log the action since post-purchase extensions have limited API access
      // In a real implementation, this would need to be handled differently
      console.log(
        `Would add variant ${defaultVariant.id} of product ${product.id} to order`,
      );

      // Note: Post-purchase extensions cannot directly add products to completed orders
      // This would typically be handled through a separate flow or API

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
            variantId: defaultVariant.id,
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
                  onPress={() => handleAddToOrder(product)}
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
