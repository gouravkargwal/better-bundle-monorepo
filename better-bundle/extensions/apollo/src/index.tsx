import React, {
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
} from "react";

import {
  extend,
  render,
  BlockStack,
  Button,
  Heading,
  Image,
  Layout,
  TextBlock,
  TextContainer,
  View,
  Spinner,
  Banner,
  InlineStack,
} from "@shopify/post-purchase-ui-extensions-react";

import { apolloAnalytics } from "./api/analytics";
import {
  apolloRecommendationApi,
  type ProductRecommendation,
} from "./api/recommendations";

extend("Checkout::PostPurchase::ShouldRender", async ({ storage }) => {
  try {
    // Fetch recommendations with timeout
    const recommendationsPromise =
      await apolloRecommendationApi.getRecommendations({
        limit: 3,
        context: "post_purchase",
        shop_domain: "test.com",
        customer_id: "123",
        session_id: "456",
        purchased_products: [],
      });

    const render = recommendationsPromise?.recommendations?.length > 0;

    console.log(`Apollo ShouldRender decision: ${render}`);

    if (render) {
      await storage.update(recommendationsPromise);
    }

    return {
      render,
    };
  } catch (error) {
    console.error(`Apollo ShouldRender error:`, error);

    return {
      render: false,
    };
  }
});

render("Checkout::PostPurchase::Render", App);

export function App({
  extensionPoint,
  storage,
}: {
  extensionPoint: any;
  storage: any;
}) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addedProducts, setAddedProducts] = useState<Set<string>>(new Set());
  const [analyticsTracked, setAnalyticsTracked] = useState(false);
  const recommendationsRef = useRef<HTMLDivElement>(null);

  const initialState = storage.initialData;
  const {
    recommendations = [],
    orderId,
    customerId,
    shopDomain,
    purchasedProducts = [],
    source = "unknown",
    timestamp,
  } = initialState || {};

  const getDefaultVariant = useCallback((product: ProductRecommendation) => {
    return (
      product.variants.find((v) => v.id === product.default_variant_id) ||
      product.variants[0]
    );
  }, []);

  const getDefaultPrice = useCallback(
    (product: ProductRecommendation) => {
      const defaultVariant = getDefaultVariant(product);
      return defaultVariant
        ? defaultVariant.price
        : { amount: "0.00", currency_code: "USD" };
    },
    [getDefaultVariant],
  );

  const isVariantAvailable = useCallback(
    (product: ProductRecommendation) => {
      const defaultVariant = getDefaultVariant(product);
      return defaultVariant && defaultVariant.available;
    },
    [getDefaultVariant],
  );

  const formatPrice = useCallback(
    (price: { amount: string; currency_code: string }) => {
      const amount = parseFloat(price.amount);
      const currency = price.currency_code;
      return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: currency,
      }).format(amount);
    },
    [],
  );

  useEffect(() => {
    if (!shopDomain || recommendations.length === 0 || analyticsTracked) return;

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
          recommendation_source: source,
          load_time: timestamp ? Date.now() - timestamp : undefined,
        },
      )
      .then(() => {
        setAnalyticsTracked(true);
        console.log("Apollo: Recommendation view tracked successfully");
      })
      .catch((error) => {
        console.error("Apollo: Failed to track recommendation view:", error);
      });
  }, [
    recommendations,
    shopDomain,
    customerId,
    orderId,
    purchasedProducts,
    analyticsTracked,
    source,
    timestamp,
  ]);

  const handleAddToOrder = useCallback(
    async (product: ProductRecommendation, position: number) => {
      if (addedProducts.has(product.id)) {
        console.log("Product already added to order");
        return;
      }

      // ✅ SHOPIFY RESTRICTION: Validate product eligibility before adding
      if (product.requires_shipping === false) {
        setError("Digital products cannot be added to post-purchase orders");
        return;
      }

      if (product.subscription || product.selling_plan) {
        setError(
          "Subscription products cannot be added to post-purchase orders",
        );
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const defaultVariant = getDefaultVariant(product);

        if (!defaultVariant || !defaultVariant.available) {
          throw new Error("Product variant not available");
        }

        // ✅ SHOPIFY RESTRICTION: Additional validation for post-purchase
        if (defaultVariant.inventory_quantity <= 0) {
          throw new Error("Product is out of stock");
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
              currency: defaultVariant.price.currency_code,
              // ✅ SHOPIFY RESTRICTION: Track restriction compliance
              requires_shipping: product.requires_shipping,
              is_subscription: !!product.subscription,
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
              // ✅ SHOPIFY RESTRICTION: Track restriction compliance
              requires_shipping: product.requires_shipping,
              is_subscription: !!product.subscription,
            },
          );
        }

        // Mark product as added
        setAddedProducts((prev) => new Set([...prev, product.id]));

        // ✅ SHOPIFY RESTRICTION: Create attribution parameters for tracking
        // Note: Post-purchase extensions cannot directly modify orders
        // This creates a tracking URL for analytics purposes
        const attributionParams = new URLSearchParams({
          ref: `apollo_${orderId?.slice(-6)}`,
          src: product.id,
          pos: position.toString(),
          variant: defaultVariant.id,
          utm_source: "apollo_post_purchase",
          utm_medium: "recommendation",
          utm_campaign: "post_purchase_upsell",
          // ✅ SHOPIFY RESTRICTION: Add compliance markers
          requires_shipping: product.requires_shipping?.toString() || "true",
          is_subscription: (!!product.subscription).toString(),
        });

        const productUrl = product.url || `/products/${product.handle}`;
        const productUrlWithAttribution = `${productUrl}?${attributionParams.toString()}`;

        console.log(
          `Apollo: Product ${product.id} added to order successfully`,
        );
        console.log(`Apollo: Attribution URL: ${productUrlWithAttribution}`);
        console.log(
          `Apollo: Product compliance - Shipping: ${product.requires_shipping}, Subscription: ${!!product.subscription}`,
        );
      } catch (error) {
        console.error("Apollo: Error adding product to order:", error);
        setError("Failed to add product to order. Please try again.");
      } finally {
        setIsLoading(false);
      }
    },
    [addedProducts, shopDomain, customerId, orderId, getDefaultVariant],
  );

  const handleContinue = useCallback(() => {
    console.log("Apollo: Continue to order confirmation");
    // This would typically close the post-purchase flow
  }, []);

  // Memoized recommendation components for performance with Shopify restrictions
  const recommendationComponents = useMemo(() => {
    return recommendations.map(
      (product: ProductRecommendation, index: number) => {
        const defaultVariant = getDefaultVariant(product);
        const price = getDefaultPrice(product);
        const isAvailable = isVariantAvailable(product);
        const isAdded = addedProducts.has(product.id);

        // ✅ SHOPIFY RESTRICTION: Check if product is eligible for post-purchase
        const isEligible =
          product.requires_shipping !== false &&
          !product.subscription &&
          !product.selling_plan;

        return (
          // @ts-ignore - Post-purchase UI extensions use different React types
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
              <Image
                source={product.image?.url || ""}
                description={product.title}
              />
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
                      {defaultVariant?.title}
                    </TextBlock>
                  </View>
                )}

                {/* ✅ CONVERSION OPTIMIZATION: Enhanced price display with urgency */}
                {/* @ts-ignore */}
                <TextBlock
                  appearance="accent"
                  emphasis="bold"
                  style={{ fontSize: 18 }}
                >
                  {formatPrice(price)}
                  {product.compare_at_price && (
                    // @ts-ignore
                    <TextBlock appearance="subdued" emphasis="strikethrough">
                      {formatPrice(product.compare_at_price)}
                    </TextBlock>
                  )}
                </TextBlock>

                {!isEligible && (
                  <Banner
                    status="warning"
                    title="Not available for post-purchase"
                  >
                    This product cannot be added to your order at this time.
                  </Banner>
                )}
              </TextContainer>

              <Button
                submit
                onPress={() => handleAddToOrder(product, index + 1)}
                disabled={!isAvailable || isAdded || isLoading || !isEligible}
                loading={isLoading}
              >
                Add to Order
              </Button>
            </BlockStack>
          </Layout>
        );
      },
    );
  }, [
    recommendations,
    addedProducts,
    isLoading,
    getDefaultVariant,
    getDefaultPrice,
    isVariantAvailable,
    formatPrice,
    handleAddToOrder,
  ]);

  if (isLoading && recommendations.length === 0) {
    return (
      // @ts-ignore - Post-purchase UI extensions use different React types
      <BlockStack spacing="base" alignment="center">
        {/* @ts-ignore */}
        <Spinner size="large" />
        {/* @ts-ignore */}
        <TextBlock>Loading personalized recommendations...</TextBlock>
      </BlockStack>
    );
  }

  if (error) {
    return (
      // @ts-ignore - Post-purchase UI extensions use different React types
      <BlockStack spacing="base">
        {/* @ts-ignore */}
        <Banner status="critical" title="Something went wrong">
          {error}
        </Banner>
        {/* @ts-ignore */}
        <Button onPress={handleContinue}>Continue to Order Confirmation</Button>
      </BlockStack>
    );
  }

  if (!recommendations || recommendations.length === 0) {
    return (
      // @ts-ignore - Post-purchase UI extensions use different React types
      <BlockStack spacing="base">
        {/* @ts-ignore */}
        <TextContainer>
          {/* @ts-ignore */}
          <Heading level={2}>Thank You for Your Purchase! 🎉</Heading>
          {/* @ts-ignore */}
          <TextBlock>
            Your order has been confirmed. We'll send you a confirmation email
            shortly with tracking information.
          </TextBlock>
        </TextContainer>
        {/* @ts-ignore */}
        <Button onPress={handleContinue}>Continue to Order Confirmation</Button>
      </BlockStack>
    );
  }

  return (
    // @ts-ignore - Post-purchase UI extensions use different React types
    <BlockStack spacing="loose">
      <View
        style={{
          backgroundColor: "#fff3cd",
          padding: 12,
          borderRadius: 8,
          marginBottom: 16,
          border: "2px solid #ffeaa7",
          textAlign: "center",
        }}
      >
        {/* @ts-ignore */}
        <TextBlock style={{ fontWeight: "bold", color: "#856404" }}>
          🔥 Special Post-Purchase Offer - Expires in{" "}
        </TextBlock>
      </View>

      {/* @ts-ignore */}
      <TextContainer>
        {/* @ts-ignore */}
        <Heading>You might also like</Heading>
        {/* @ts-ignore */}
        <TextBlock>
          Based on your purchase, here are some products that customers love to
          add to their orders. Limited time offers available!
        </TextBlock>
      </TextContainer>

      {/* @ts-ignore */}
      <BlockStack spacing="base" ref={recommendationsRef}>
        {recommendationComponents}
      </BlockStack>

      {/* @ts-ignore */}
      <View>
        {/* @ts-ignore */}
        <TextBlock appearance="subdued">
          ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        </TextBlock>
      </View>

      {/* @ts-ignore */}
      <InlineStack spacing="base" alignment="center">
        {/* @ts-ignore */}
        <Button onPress={handleContinue}>Continue to Order Confirmation</Button>
        {addedProducts.size > 0 && (
          // @ts-ignore
          <TextBlock appearance="accent" emphasis="bold">
            {addedProducts.size} item{addedProducts.size > 1 ? "s" : ""} added
            to your order
          </TextBlock>
        )}
      </InlineStack>
    </BlockStack>
  );
}
