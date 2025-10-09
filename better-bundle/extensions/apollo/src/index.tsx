/**
 * Apollo Post-Purchase Extension
 *
 * This extension follows Shopify's Post-Purchase API best practices:
 * - Uses inputData from Shopify instead of hardcoded values
 * - Implements proper changeset handling for adding products to orders
 * - Includes comprehensive error handling for post-purchase restrictions
 * - Validates products against actual Shopify order data
 * - Uses proper storage and session management
 *
 * Key Features:
 * - Cross-sell recommendations based on purchased products
 * - Real-time price calculation with changeset API
 * - Comprehensive error handling for all Shopify restrictions
 * - Analytics tracking for recommendation performance
 * - Proper post-purchase flow completion
 */

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

extend(
  "Checkout::PostPurchase::ShouldRender",
  async ({ inputData, storage }) => {
    try {
      // Extract data from Shopify's inputData
      const { initialPurchase, shop, locale } = inputData;
      const shopDomain = shop.domain;
      const customerId = initialPurchase.customerId;
      const orderId = initialPurchase.referenceId;

      // Extract purchased products from line items
      const purchasedProducts = initialPurchase.lineItems.map((item) => ({
        id: item.product.id.toString(),
        title: item.product.title,
        variant: item.product.variant,
        quantity: item.quantity,
        totalPrice: item.totalPriceSet,
      }));

      console.log(
        `Apollo ShouldRender - Shop: ${shopDomain}, Customer: ${customerId}, Order: ${orderId}`,
      );
      console.log(
        `Apollo ShouldRender - Purchased products: ${purchasedProducts.length} items`,
      );

      // Use the new combined API for better performance
      const result = await apolloRecommendationApi.getSessionAndRecommendations(
        shopDomain,
        customerId,
        orderId,
        purchasedProducts.map((p: any) => p.id), // Use actual purchased product IDs
        3, // limit
        {
          source: "apollo_post_purchase",
          locale,
          shopId: shop.id,
          totalPrice: initialPurchase.totalPriceSet,
          lineItemCount: initialPurchase.lineItems.length,
        },
      );

      const render = result.success && result.recommendations?.length > 0;

      console.log(`Apollo ShouldRender decision: ${render}`);
      console.log(`Apollo Session ID: ${result.sessionId}`);
      console.log(
        `Apollo Recommendations: ${result.recommendations?.length || 0} items`,
      );

      if (render) {
        // Store both session and recommendations data
        await storage.update({
          recommendations: result.recommendations,
          sessionId: result.sessionId,
          orderId,
          customerId,
          shopDomain,
          purchasedProducts,
          source: "apollo_combined_api",
          timestamp: Date.now(),
          // Store Shopify-specific data
          shop,
          locale,
          initialPurchase: {
            referenceId: initialPurchase.referenceId,
            totalPriceSet: initialPurchase.totalPriceSet,
            lineItems: initialPurchase.lineItems,
          },
        });
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
  },
);

render("Checkout::PostPurchase::Render", App);

export function App({
  extensionPoint,
  storage,
  inputData,
  calculateChangeset,
  applyChangeset,
  done,
}: {
  extensionPoint: any;
  storage: any;
  inputData: any;
  calculateChangeset: any;
  applyChangeset: any;
  done: any;
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
    shop,
    locale,
    initialPurchase,
  } = initialState || {};

  const getDefaultVariant = useCallback((product: ProductRecommendation) => {
    const variants = (product as any).variants || [];
    const selectedId =
      (product as any).selectedVariantId || (product as any).variant_id;
    const raw =
      variants.find((v: any) => (v.id || v.variant_id) === selectedId) ||
      variants[0];
    if (!raw) return null;

    const variantId = (raw.id || raw.variant_id) as string;
    const priceNumber =
      typeof raw.price === "number"
        ? raw.price
        : parseFloat(raw.price?.amount ?? "0");
    const currency =
      raw.currency_code || (product as any).price?.currency_code || "USD";
    const inventoryQty =
      typeof raw.inventory === "number"
        ? raw.inventory
        : (raw.inventory_quantity ?? 0);

    return {
      ...raw,
      id: variantId,
      price: { amount: priceNumber.toString(), currency_code: currency },
      inventory_quantity: inventoryQty,
      available: (product as any).available !== false && inventoryQty > 0,
      title: raw.title,
    } as any;
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

      // ✅ SHOPIFY RESTRICTION: Check if product is already in the order
      const isAlreadyPurchased = purchasedProducts.some(
        (p: any) => p.id === product.id,
      );
      if (isAlreadyPurchased) {
        setError("This product is already in your order");
        return;
      }

      // Removed validation against initialPurchase; rely on backend response for accuracy

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

        // ✅ SHOPIFY API: Create changeset to add product to order
        const changeset = {
          changes: [
            {
              type: "add_variant",
              variantId: parseInt(defaultVariant.id),
              quantity: 1,
              // Optional: Add discount for post-purchase offers
              discount: {
                value: 10, // 10% discount
                valueType: "percentage",
                title: "Post-purchase special offer",
              },
            },
          ],
        };

        // Calculate changeset to show price impact
        console.log("Apollo: Calculating changeset for product", product.id);
        const calculationResult = await calculateChangeset(changeset);

        if (calculationResult.status === "unprocessed") {
          const errorMessages = calculationResult.errors
            .map((err: any) => {
              // Handle specific Shopify error codes
              switch (err.code) {
                case "insufficient_inventory":
                  return "This product is out of stock";
                case "payment_required":
                  return "Payment is required to add this product";
                case "unsupported_payment_method":
                  return "Your payment method doesn't support adding products";
                case "subscription_vaulting_error":
                  return "Cannot add subscription products to post-purchase orders";
                default:
                  return err.message;
              }
            })
            .join(", ");
          throw new Error(`Cannot add product: ${errorMessages}`);
        }

        console.log(
          "Apollo: Changeset calculation successful",
          calculationResult.calculatedPurchase,
        );

        // Apply the changeset to actually add the product
        console.log("Apollo: Applying changeset to add product", product.id);
        const applyResult = await applyChangeset(JSON.stringify(changeset), {
          buyerConsentToSubscriptions: false, // Post-purchase doesn't support subscriptions
        });

        if (applyResult.status === "unprocessed") {
          const errorMessages = applyResult.errors
            .map((err: any) => {
              // Handle specific Shopify error codes for apply changeset
              switch (err.code) {
                case "changeset_already_applied":
                  return "This product has already been added to your order";
                case "insufficient_inventory":
                  return "This product is no longer available";
                case "payment_required":
                  return "Payment authorization is required";
                case "order_released_error":
                  return "Your order has been processed and cannot be modified";
                default:
                  return err.message;
              }
            })
            .join(", ");
          throw new Error(`Failed to add product: ${errorMessages}`);
        }

        // Track successful add to order action
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
              changeset_applied: true,
              new_total:
                applyResult.calculatedPurchase?.totalPriceSet?.shopMoney
                  ?.amount,
            },
          );
        }

        // Mark product as added
        setAddedProducts((prev) => new Set([...prev, product.id]));

        console.log(
          `Apollo: Product ${product.id} successfully added to order via changeset`,
        );
        console.log(
          `Apollo: New order total: ${applyResult.calculatedPurchase?.totalPriceSet?.shopMoney?.amount} ${applyResult.calculatedPurchase?.totalPriceSet?.shopMoney?.currencyCode}`,
        );
      } catch (error) {
        console.error("Apollo: Error adding product to order:", error);
        setError(`Failed to add product to order: ${(error as Error).message}`);
      } finally {
        setIsLoading(false);
      }
    },
    [
      addedProducts,
      shopDomain,
      customerId,
      orderId,
      getDefaultVariant,
      calculateChangeset,
      applyChangeset,
    ],
  );

  const handleContinue = useCallback(async () => {
    console.log("Apollo: Continue to order confirmation");
    try {
      // Use Shopify's done() API to properly close the post-purchase flow
      await done();
      console.log("Apollo: Post-purchase flow completed successfully");
    } catch (error) {
      console.error("Apollo: Error completing post-purchase flow:", error);
      setError("Failed to complete order. Please try again.");
    }
  }, [done]);

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
