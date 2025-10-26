import { useState, useCallback, useEffect } from "react";
import type { StorageData, ProductRecommendationAPI } from "./types";
import { isProductEligible, getShopifyErrorMessage } from "./utils/utils";
import { apolloAnalytics } from "./api/analytics";
import { apolloRecommendationApi } from "./api/recommendations";
import { ImageCarousel } from "./components/ImageCarousel";
import { JWTManager } from "./utils/jwtManager";
import {
  BlockStack,
  Button,
  Heading,
  TextBlock,
  TextContainer,
  Spinner,
  Banner,
  InlineStack,
  CalloutBanner,
  Separator,
  Layout,
  View,
  Select,
  Text,
} from "@shopify/post-purchase-ui-extensions-react";
import { logger } from "./utils/logger";
import { SHOPIFY_APP_URL } from "./constant";
function App({ storage, calculateChangeset, applyChangeset, done }: any) {
  // State management
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentOfferIndex, setCurrentOfferIndex] = useState(0);
  const [addedProducts, setAddedProducts] = useState<Set<string>>(new Set());
  const [selectedOptions, setSelectedOptions] = useState<
    Record<string, Record<string, string>>
  >({});
  const [quantities, setQuantities] = useState<Record<string, number>>({});
  const [calculatedPurchase, setCalculatedPurchase] = useState<any>(null);
  const [isCalculating, setIsCalculating] = useState(false);
  const [jwtManager, setJwtManager] = useState<JWTManager | null>(null);

  // Extract storage data
  const initialState: StorageData = storage.initialData || {};
  const {
    recommendations = [],
    sessionId,
    orderId,
    customerId,
    shopDomain,
    purchasedProducts = [],
  } = initialState;

  // Initialize JWT Manager with storage
  useEffect(() => {
    if (shopDomain && storage) {
      console.log("🚀 Apollo: Creating JWT Manager in App component");
      const jwt = new JWTManager(storage);
      setJwtManager(jwt);

      // Set JWT manager on API clients
      apolloRecommendationApi.setJWTManager(jwt);
      apolloAnalytics.setJWTManager(jwt);
    }
  }, [shopDomain, storage]);

  // Maximum consecutive offers per Shopify guidelines
  const MAX_OFFERS = 3;

  // Get current product to display
  const currentProduct = recommendations[currentOfferIndex] || null;

  // Helper functions
  const getDefaultVariant = useCallback((product: ProductRecommendationAPI) => {
    // Find the first available variant instead of just the first variant
    return (
      product.variants?.find(
        (variant: any) => variant.inventory > 0 && variant.available !== false,
      ) ||
      product.variants?.[0] ||
      null
    );
  }, []);

  // Get variant by selected options
  const getVariantByOptions = useCallback(
    (product: ProductRecommendationAPI, options: Record<string, string>) => {
      if (!product.variants || Object.keys(options).length === 0) {
        return getDefaultVariant(product);
      }

      return (
        product.variants.find((variant: any) => {
          const variantTitle = variant.title || "";
          const optionValues = Object.values(options);
          return optionValues.every((value) =>
            variantTitle.toLowerCase().includes(value.toLowerCase()),
          );
        }) || getDefaultVariant(product)
      );
    },
    [getDefaultVariant],
  );

  const isVariantAvailable = useCallback((variant: any) => {
    return variant && variant.inventory > 0 && variant.available !== false;
  }, []);

  const formatPrice = useCallback((price: number, currency: string = "USD") => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency,
    }).format(price);
  }, []);

  // Handle option selection
  const handleOptionChange = useCallback(
    (
      productId: string,
      optionName: string,
      value: string,
      product: ProductRecommendationAPI,
    ) => {
      setSelectedOptions((prev) => {
        const productOptions = prev[productId] || {};
        const newOptions = {
          ...productOptions,
          [optionName]: value,
        };
        return {
          ...prev,
          [productId]: newOptions,
        };
      });
    },
    [],
  );

  // Handle quantity change
  const handleQuantityChange = useCallback(
    (productId: string, quantity: number) => {
      setQuantities((prev) => ({
        ...prev,
        [productId]: Math.max(1, quantity),
      }));
    },
    [],
  );

  // Get current variant for a product based on selected options
  const getCurrentVariant = useCallback(
    (product: ProductRecommendationAPI) => {
      const productOptions = selectedOptions[product.id] || {};
      return getVariantByOptions(product, productOptions);
    },
    [selectedOptions, getVariantByOptions],
  );

  // Get current quantity for a product
  const getCurrentQuantity = useCallback(
    (productId: string) => {
      return quantities[productId] || 1;
    },
    [quantities],
  );

  // Get available option values based on other selected options
  const getAvailableOptionValues = useCallback(
    (product: ProductRecommendationAPI, targetOptionName: string) => {
      if (!product.variants || !product.options) return [];

      const productOptions = selectedOptions[product.id] || {};
      const targetOptionIndex = product.options.findIndex(
        (opt) => opt.name === targetOptionName,
      );

      if (targetOptionIndex === -1) return [];

      const availableValues = new Set<string>();

      product.variants.forEach((variant: any) => {
        if (variant.inventory <= 0) return;

        const variantTitle = variant.title || "";
        const parts = variantTitle.split(" / ").map((p) => p.trim());

        const matchesOtherOptions = product.options.every(
          (opt: any, idx: number) => {
            if (opt.name === targetOptionName) return true;

            const selectedValue = productOptions[opt.name];
            if (!selectedValue) return true;

            return (
              parts[idx] &&
              parts[idx].toLowerCase() === selectedValue.toLowerCase()
            );
          },
        );

        if (matchesOtherOptions && parts[targetOptionIndex]) {
          availableValues.add(parts[targetOptionIndex]);
        }
      });

      return Array.from(availableValues);
    },
    [selectedOptions],
  );

  // Handle declining an offer - show next product or complete
  const handleDecline = useCallback(async () => {
    // Track decline
    if (shopDomain && sessionId && currentProduct && jwtManager) {
      await apolloAnalytics.trackRecommendationDecline(
        shopDomain,
        sessionId,
        currentProduct.id,
        currentOfferIndex + 1,
        currentProduct, // Pass full product data
        {
          source: "apollo_post_purchase",
          customer_id: customerId,
          order_id: orderId,
          decline_reason: "user_declined",
        },
      );
    }

    const nextIndex = currentOfferIndex + 1;

    // Check if we should show another offer
    if (
      nextIndex < recommendations.length &&
      nextIndex < MAX_OFFERS &&
      addedProducts.size === 0
    ) {
      // Show next offer
      setCurrentOfferIndex(nextIndex);
      setError(null);
    } else {
      await done();
    }
  }, [
    currentOfferIndex,
    recommendations,
    addedProducts,
    currentProduct,
    shopDomain,
    sessionId,
    customerId,
    orderId,
    jwtManager,
    done,
  ]);

  // Initialize selected options with first available variant
  useEffect(() => {
    if (currentProduct && currentProduct.variants && currentProduct.options) {
      const firstAvailableVariant = currentProduct.variants.find(
        (variant: any) => variant.inventory > 0 && variant.available !== false,
      );

      if (firstAvailableVariant && firstAvailableVariant.title) {
        const variantTitle = firstAvailableVariant.title;
        const parts = variantTitle.split(" / ").map((p: string) => p.trim());

        const newOptions: Record<string, string> = {};
        currentProduct.options.forEach((option: any, index: number) => {
          if (parts[index]) {
            newOptions[option.name] = parts[index];
          }
        });

        setSelectedOptions((prev) => ({
          ...prev,
          [currentProduct.id]: newOptions,
        }));
      }
    }
  }, [currentProduct]);

  // Real-time pricing calculation
  useEffect(() => {
    async function calculatePricing() {
      if (
        !currentProduct ||
        !getCurrentVariant(currentProduct) ||
        getCurrentQuantity(currentProduct.id) <= 0
      ) {
        setCalculatedPurchase(null);
        return;
      }

      setIsCalculating(true);

      try {
        const product = currentProduct;
        const currentVariant = getCurrentVariant(product);
        const currentQuantity = getCurrentQuantity(product.id);

        if (!currentVariant || currentQuantity <= 0) {
          setCalculatedPurchase(null);
          return;
        }

        const changeset = {
          changes: [
            {
              type: "add_variant",
              variantId: parseInt(currentVariant.variant_id),
              quantity: currentQuantity,
            },
          ],
        };

        const calculationResult = await calculateChangeset(changeset);

        if (calculationResult.status === "processed") {
          setCalculatedPurchase(calculationResult.calculatedPurchase);
        } else {
          setCalculatedPurchase(null);
        }
      } catch (error) {
        logger.error("Error calculating real-time pricing:", error);
        setCalculatedPurchase(null);
      } finally {
        setIsCalculating(false);
      }
    }

    calculatePricing();
  }, [
    currentProduct,
    selectedOptions,
    quantities,
    getCurrentVariant,
    getCurrentQuantity,
    calculateChangeset,
  ]);

  // Main add to order handler
  const handleAddToOrder = useCallback(
    async (product: ProductRecommendationAPI, position: number) => {
      if (addedProducts.has(product.id)) {
        return;
      }

      if (!isProductEligible(product)) {
        setError("This product is not available for purchase");
        return;
      }

      const isAlreadyPurchased = purchasedProducts.some(
        (p: any) => p.id === product.id,
      );
      if (isAlreadyPurchased) {
        setError("This product is already in your order");
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const selectedVariant = getCurrentVariant(product);
        const quantity = getCurrentQuantity(product.id);

        if (!selectedVariant || !isVariantAvailable(selectedVariant)) {
          throw new Error("Product variant not available");
        }

        if (selectedVariant.inventory < quantity) {
          throw new Error(
            `Only ${selectedVariant.inventory} items available in stock`,
          );
        }

        // Validate variant ID and quantity before creating changeset
        if (
          !selectedVariant.variant_id ||
          isNaN(parseInt(selectedVariant.variant_id))
        ) {
          throw new Error("Invalid variant ID");
        }

        if (!quantity || quantity <= 0 || !Number.isInteger(quantity)) {
          throw new Error("Invalid quantity");
        }

        // Track recommendation click
        if (shopDomain && sessionId && jwtManager) {
          await apolloAnalytics.trackRecommendationClick(
            shopDomain,
            sessionId,
            product.id,
            position,
            {
              source: "apollo_post_purchase",
              customer_id: customerId,
              order_id: orderId,
              variant_id: selectedVariant.variant_id,
              product_title: product.title,
              variant_title: selectedVariant.title,
              price: selectedVariant.price.toString(),
              currency: selectedVariant.currency_code,
              sku: selectedVariant.sku,
              inventory: selectedVariant.inventory,
              quantity: quantity,
            },
          );
        }

        // Create changeset - include session ID in order metafields for attribution
        const variantId = parseInt(selectedVariant.variant_id);
        const changeset = {
          changes: [
            {
              type: "add_variant",
              variantId: variantId,
              quantity: quantity,
            },
            // ✅ ADD SESSION ID TO ORDER METAFIELDS FOR ATTRIBUTION (following Phoenix pattern)
            {
              type: "set_metafield",
              namespace: "bb_recommendation",
              key: "session_id",
              value: sessionId,
              valueType: "string",
            },
            {
              type: "set_metafield",
              namespace: "bb_recommendation",
              key: "extension",
              value: "apollo",
              valueType: "string",
            },
            {
              type: "set_metafield",
              namespace: "bb_recommendation",
              key: "context",
              value: "post_purchase",
              valueType: "string",
            },
            {
              type: "set_metafield",
              namespace: "bb_recommendation",
              key: "position",
              value: position.toString(),
              valueType: "string",
            },
            {
              type: "set_metafield",
              namespace: "bb_recommendation",
              key: "quantity",
              value: quantity.toString(),
              valueType: "string",
            },
            {
              type: "set_metafield",
              namespace: "bb_recommendation",
              key: "timestamp",
              value: new Date().toISOString(),
              valueType: "string",
            },
            {
              type: "set_metafield",
              namespace: "bb_recommendation",
              key: "source",
              value: "betterbundle",
              valueType: "string",
            },
          ],
        };

        // Final validation - ensure changeset has valid structure
        if (!changeset.changes || changeset.changes.length === 0) {
          throw new Error("Invalid changeset: no changes provided");
        }

        const change = changeset.changes[0];
        if (!change.type || !change.variantId || !change.quantity) {
          throw new Error("Invalid changeset: missing required fields");
        }

        const calculationResult = await calculateChangeset(changeset);

        if (calculationResult.status === "unprocessed") {
          const errorMessages = calculationResult.errors
            .map((err: any) => getShopifyErrorMessage(err.code))
            .join(", ");
          throw new Error(`Cannot add product: ${errorMessages}`);
        }

        // Check if calculation was successful
        if (calculationResult.status !== "processed") {
          throw new Error("Changeset calculation failed");
        }

        // Pricing already calculated in real-time, no need to store again

        const tokenResponse = await fetch(
          `${SHOPIFY_APP_URL}/api/sign-changeset`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              referenceId: orderId,
              changes: changeset.changes,
            }),
          },
        );

        if (!tokenResponse.ok) {
          throw new Error("Failed to get signed token from backend");
        }

        const { token } = await tokenResponse.json();
        if (!token) {
          throw new Error("No token received from backend");
        }

        const applyResult = await applyChangeset(token, {
          buyerConsentToSubscriptions: false,
        });

        if (applyResult.status === "unprocessed") {
          const errorMessages = applyResult.errors
            .map((err: any) => getShopifyErrorMessage(err.code))
            .join(", ");
          throw new Error(`Failed to add product: ${errorMessages}`);
        }

        // Track successful add to order
        if (shopDomain && sessionId && jwtManager) {
          await apolloAnalytics.trackAddToOrder(
            shopDomain,
            sessionId,
            product.id,
            selectedVariant.variant_id,
            position,
            {
              source: "apollo_post_purchase",
              customer_id: customerId,
              order_id: orderId,
              product_title: product.title,
              variant_title: selectedVariant.title,
              price: selectedVariant.price.toString(),
              currency: selectedVariant.currency_code,
              quantity: quantity,
              changeset_applied: true,
              new_total:
                applyResult.calculatedPurchase?.totalPriceSet?.shopMoney
                  ?.amount,
            },
          );
        }

        setAddedProducts((prev) => new Set([...prev, product.id]));

        // Auto-continue after adding to order
        await done();
      } catch (error) {
        logger.error("Error adding product:", error);
        setError((error as Error).message);
      } finally {
        setIsLoading(false);
      }
    },
    [
      addedProducts,
      shopDomain,
      sessionId,
      customerId,
      orderId,
      purchasedProducts,
      getCurrentVariant,
      getCurrentQuantity,
      isVariantAvailable,
      jwtManager,
      calculateChangeset,
      applyChangeset,
      done,
    ],
  );

  // Loading state
  if (isLoading && recommendations.length === 0) {
    return (
      // @ts-ignore
      <BlockStack spacing="base" alignment="center">
        {/* @ts-ignore */}
        <Spinner size="large" />
        {/* @ts-ignore */}
        <TextContainer alignment="center">
          {/* @ts-ignore */}
          <TextBlock>Loading personalized recommendations...</TextBlock>
        </TextContainer>
      </BlockStack>
    );
  }

  // Empty state or no current product
  if (!recommendations || recommendations.length === 0 || !currentProduct) {
    return (
      // @ts-ignore
      <BlockStack spacing="base">
        {/* @ts-ignore */}
        <TextContainer>
          {/* @ts-ignore */}
          <Heading>Thank You for Your Purchase!</Heading>
          {/* @ts-ignore */}
          <TextBlock>
            Your order has been confirmed. We'll send you tracking information
            shortly.
          </TextBlock>
        </TextContainer>
        {/* @ts-ignore */}
        <Button onPress={done}>Continue to Order Confirmation</Button>
      </BlockStack>
    );
  }

  // Render single product offer
  const product = currentProduct;
  const currentVariant = getCurrentVariant(product);
  const currentQuantity = getCurrentQuantity(product.id);
  const isAdded = addedProducts.has(product.id);
  const isAvailable = currentVariant && isVariantAvailable(currentVariant);
  const hasMultipleVariants = (product.variants?.length || 0) > 1;
  const productOptions = selectedOptions[product.id] || {};

  // Calculate price breakdown using actual Shopify calculations
  const itemPrice = currentVariant ? currentVariant.price * currentQuantity : 0;

  // Use actual values from calculateChangeset response
  const shipping = calculatedPurchase?.addedShippingLines?.[0]?.priceSet
    ?.presentmentMoney?.amount
    ? parseFloat(
        calculatedPurchase.addedShippingLines[0].priceSet.presentmentMoney
          .amount,
      )
    : 0;

  const tax =
    calculatedPurchase?.addedTaxLines?.reduce((total: number, taxLine: any) => {
      return (
        total + parseFloat(taxLine.priceSet?.presentmentMoney?.amount || 0)
      );
    }, 0) || 0;

  // For post-purchase upsells, use item price for subtotal to show only upsell amount
  // subtotalPriceSet might include the original order items
  const subtotal = itemPrice;

  // For post-purchase upsells, we want to show only the additional amount
  // Use totalOutstandingSet which shows what the customer needs to pay for the upsell
  const total = calculatedPurchase?.totalOutstandingSet?.presentmentMoney
    ?.amount
    ? parseFloat(calculatedPurchase.totalOutstandingSet.presentmentMoney.amount)
    : subtotal + shipping + tax;

  // Get currency from calculated purchase or fallback to variant currency
  const currency =
    calculatedPurchase?.totalOutstandingSet?.presentmentMoney?.currencyCode ||
    currentVariant?.currency_code ||
    "USD";

  // Show fallback pricing if calculation is not available
  const showFallbackPricing = !calculatedPurchase && !isCalculating;

  return (
    // @ts-ignore
    <BlockStack spacing="loose">
      {/* CALLOUT BANNER - Required by Shopify UX guidelines */}
      {/* @ts-ignore */}
      <CalloutBanner title="Complete your order">
        Add this recommended product to your order
      </CalloutBanner>

      {/* Progress indicator */}
      {recommendations.length > 1 && (
        // @ts-ignore
        <TextContainer alignment="center">
          {/* @ts-ignore */}
          <TextBlock appearance="subdued" size="small">
            Recommendation {currentOfferIndex + 1} of{" "}
            {Math.min(recommendations.length, MAX_OFFERS)}
          </TextBlock>
        </TextContainer>
      )}

      {/* Error Banner */}
      {error && (
        // @ts-ignore
        <Banner status="critical" title="Error">
          {error}
        </Banner>
      )}

      {/* Single Product Offer */}
      {/* @ts-ignore */}
      <Layout
        maxInlineSize={0.95}
        media={[
          { viewportSize: "small", sizes: [1, 20, 1] },
          { viewportSize: "medium", sizes: [400, 20, 0.4] },
          { viewportSize: "large", sizes: [500, 20, 0.3] },
        ]}
      >
        {/* Product Image Carousel */}
        {/* @ts-ignore */}
        <View>
          {/* @ts-ignore */}
          <ImageCarousel
            images={product.images || (product.image ? [product.image] : [])}
            productTitle={product.title}
          />
        </View>

        {/* Spacer */}
        {/* @ts-ignore */}
        <View />

        {/* Product Details */}
        {/* @ts-ignore */}
        <BlockStack spacing="base">
          {/* 1. PRODUCT TITLE AND PRICE */}
          {/* @ts-ignore */}
          <TextContainer>
            {/* @ts-ignore */}
            <Heading level={2}>{product.title}</Heading>

            {currentVariant && (
              // @ts-ignore
              <InlineStack spacing="tight">
                {/* @ts-ignore */}
                <Text size="large" emphasis="bold">
                  {formatPrice(
                    currentVariant.price,
                    currentVariant.currency_code,
                  )}
                </Text>
                {product.compare_at_price && (
                  // @ts-ignore
                  <Text appearance="subdued" emphasis="strikethrough">
                    {formatPrice(
                      product.compare_at_price,
                      currentVariant.currency_code,
                    )}
                  </Text>
                )}
              </InlineStack>
            )}
          </TextContainer>

          {/* 2. PRODUCT DESCRIPTION */}
          {product.description && (
            // @ts-ignore
            <TextBlock appearance="subdued">{product.description}</TextBlock>
          )}

          {/* 3. VARIANT PICKER */}
          {hasMultipleVariants &&
            product.options &&
            product.options.length > 0 && (
              // @ts-ignore
              <BlockStack spacing="tight">
                {product.options.map((option: any) => {
                  const availableValues = getAvailableOptionValues(
                    product,
                    option.name,
                  );
                  const selectedValue =
                    productOptions[option.name] || availableValues[0] || "";

                  return (
                    // @ts-ignore
                    <Select
                      key={`${product.id}-${option.name}`}
                      label={option.name}
                      value={selectedValue}
                      onChange={(value) =>
                        handleOptionChange(
                          product.id,
                          option.name,
                          value,
                          product,
                        )
                      }
                      options={availableValues.map((value: string) => ({
                        value: value,
                        label: value,
                      }))}
                    />
                  );
                })}
              </BlockStack>
            )}

          {/* 4. QUANTITY PICKER */}
          {currentVariant && isAvailable && (
            // @ts-ignore
            <BlockStack spacing="tight">
              {/* @ts-ignore */}
              <Text>Quantity</Text>
              {/* @ts-ignore */}
              <InlineStack spacing="tight">
                {/* @ts-ignore */}
                <Button
                  plain
                  onPress={() =>
                    handleQuantityChange(product.id, currentQuantity - 1)
                  }
                  disabled={currentQuantity <= 1 || isAdded}
                >
                  −
                </Button>
                {/* @ts-ignore */}
                <View border="base" padding="base" cornerRadius="base">
                  {/* @ts-ignore */}
                  <Text emphasis="bold">{currentQuantity}</Text>
                </View>
                {/* @ts-ignore */}
                <Button
                  plain
                  onPress={() =>
                    handleQuantityChange(product.id, currentQuantity + 1)
                  }
                  disabled={
                    currentQuantity >= currentVariant.inventory || isAdded
                  }
                >
                  +
                </Button>
              </InlineStack>
            </BlockStack>
          )}

          {/* 5. PRICE BREAKDOWN */}
          {currentVariant && isAvailable && (
            // @ts-ignore
            <BlockStack spacing="tight">
              {isCalculating && (
                // @ts-ignore
                <InlineStack alignment="center" spacing="tight">
                  {/* @ts-ignore */}
                  <Spinner size="small" />
                  {/* @ts-ignore */}
                  <Text>Calculating pricing...</Text>
                </InlineStack>
              )}
              {showFallbackPricing && (
                // @ts-ignore
                <InlineStack alignment="center" spacing="tight">
                  {/* @ts-ignore */}
                  <Text emphasis="subdued">
                    Pricing will be calculated when you add to order
                  </Text>
                </InlineStack>
              )}
              {/* Money Lines */}
              {/* @ts-ignore */}
              <View>
                {/* @ts-ignore */}
                <InlineStack>
                  {/* @ts-ignore */}
                  <View>
                    {/* @ts-ignore */}
                    <Text>Subtotal</Text>
                  </View>
                  {/* @ts-ignore */}
                  <View>
                    {/* @ts-ignore */}
                    <Text alignment="end">
                      {formatPrice(subtotal, currency)}
                    </Text>
                  </View>
                </InlineStack>
              </View>

              {/* @ts-ignore */}
              <View>
                {/* @ts-ignore */}
                <InlineStack>
                  {/* @ts-ignore */}
                  <View>
                    {/* @ts-ignore */}
                    <Text>Shipping</Text>
                  </View>
                  {/* @ts-ignore */}
                  <View>
                    {/* @ts-ignore */}
                    <Text alignment="end">
                      {formatPrice(shipping, currency)}
                    </Text>
                  </View>
                </InlineStack>
              </View>

              {/* @ts-ignore */}
              <View>
                {/* @ts-ignore */}
                <InlineStack>
                  {/* @ts-ignore */}
                  <View>
                    {/* @ts-ignore */}
                    <Text>Tax</Text>
                  </View>
                  {/* @ts-ignore */}
                  <View>
                    {/* @ts-ignore */}
                    <Text alignment="end">{formatPrice(tax, currency)}</Text>
                  </View>
                </InlineStack>
              </View>

              {/* @ts-ignore */}
              <Separator />

              {/* Money Summary */}
              {/* @ts-ignore */}
              <View>
                {/* @ts-ignore */}
                <InlineStack>
                  {/* @ts-ignore */}
                  <View>
                    {/* @ts-ignore */}
                    <Text size="large" emphasis="bold">
                      Total
                    </Text>
                  </View>
                  {/* @ts-ignore */}
                  <View>
                    {/* @ts-ignore */}
                    <Text size="large" emphasis="bold" alignment="end">
                      {formatPrice(total, currency)}
                    </Text>
                  </View>
                </InlineStack>
              </View>
            </BlockStack>
          )}

          {/* Inventory Warning */}
          {currentVariant &&
            currentVariant.inventory > 0 &&
            currentVariant.inventory <= 5 && (
              // @ts-ignore
              <Banner status="warning">
                Only {currentVariant.inventory} left in stock!
              </Banner>
            )}

          {/* Out of Stock Banner */}
          {currentVariant && !isAvailable && (
            // @ts-ignore
            <Banner status="critical">
              This variant is currently out of stock
            </Banner>
          )}

          {/* 6. ACCEPT BUTTON */}
          {/* @ts-ignore */}
          <Button
            submit
            onPress={() => handleAddToOrder(product, currentOfferIndex + 1)}
            disabled={!isAvailable || isAdded || isLoading}
            loading={isLoading}
          >
            {isAdded
              ? "✓ Added to Order"
              : `Pay now · ${formatPrice(total, currency)}`}
          </Button>

          {/* 7. DECLINE BUTTON */}
          {!isAdded && (
            // @ts-ignore
            <Button onPress={handleDecline} disabled={isLoading} plain>
              No thanks
            </Button>
          )}
        </BlockStack>
      </Layout>

      {/* Success Message */}
      {addedProducts.size > 0 && (
        // @ts-ignore
        <Banner status="success">
          Product added to your order successfully!
        </Banner>
      )}
    </BlockStack>
  );
}

export default App;
