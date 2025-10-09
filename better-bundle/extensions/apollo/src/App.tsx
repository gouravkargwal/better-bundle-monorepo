import { useState, useCallback, useMemo } from "react";
import type { StorageData, ProductRecommendationAPI } from "./types";
import { isProductEligible, getShopifyErrorMessage } from "./utils/utils";
import { apolloAnalytics } from "./api/analytics";
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
  Image,
  Select,
  Text,
} from "@shopify/post-purchase-ui-extensions-react";

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

  // Extract storage data
  const initialState: StorageData = storage.initialData || {};
  const {
    recommendations = [],
    sessionId,
    orderId,
    customerId,
    shopDomain,
    purchasedProducts = [],
    source = "unknown",
  } = initialState;

  // Maximum consecutive offers per Shopify guidelines
  const MAX_OFFERS = 3;

  // Get current product to display
  const currentProduct = recommendations[currentOfferIndex] || null;

  // Helper functions
  const getDefaultVariant = useCallback((product: ProductRecommendationAPI) => {
    return product.variants?.[0] || null;
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
    console.log(
      `Apollo: Customer declined offer ${currentOfferIndex + 1}/${recommendations.length}`,
    );

    // Track decline
    if (shopDomain && sessionId && currentProduct) {
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
      console.log(`Apollo: Showing offer ${nextIndex + 1}`);
    } else {
      // No more offers or max reached, complete the flow
      console.log(
        "Apollo: Max offers reached or no more products, completing flow",
      );

      // No need to track implicit declines - user never saw these products
      // Only track actual user interactions (views, clicks, explicit declines)

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
    done,
  ]);

  // Main add to order handler
  const handleAddToOrder = useCallback(
    async (product: ProductRecommendationAPI, position: number) => {
      if (addedProducts.has(product.id)) {
        console.log("Product already added");
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

        // Track recommendation click
        if (shopDomain && sessionId) {
          const cleanShopDomain = shopDomain.replace(".myshopify.com", "");

          await apolloAnalytics.trackRecommendationClick(
            cleanShopDomain,
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

        // Build line item properties for attribution
        const itemProperties = {
          _bb_rec_session_id: sessionId || "",
          _bb_rec_product_id: product.id || "",
          _bb_rec_extension: "apollo",
          _bb_rec_context: "post_purchase",
          _bb_rec_position: String(position || ""),
          _bb_rec_timestamp: new Date().toISOString(),
          _bb_rec_source: "betterbundle",
          _bb_rec_variant_id: selectedVariant.variant_id,
          _bb_rec_score: String(product.score || ""),
        };

        // Create changeset with properties
        const changeset = {
          changes: [
            {
              type: "add_variant",
              variantId: parseInt(selectedVariant.variant_id),
              quantity: quantity,
              properties: Object.entries(itemProperties).map(
                ([key, value]) => ({ key, value }),
              ),
            },
          ],
        };

        console.log(
          "Apollo: Calculating changeset with properties:",
          itemProperties,
        );
        const calculationResult = await calculateChangeset(changeset);

        if (calculationResult.status === "unprocessed") {
          const errorMessages = calculationResult.errors
            .map((err: any) => getShopifyErrorMessage(err.code))
            .join(", ");
          throw new Error(`Cannot add product: ${errorMessages}`);
        }

        console.log("Apollo: Applying changeset");
        const applyResult = await applyChangeset(JSON.stringify(changeset), {
          buyerConsentToSubscriptions: false,
        });

        if (applyResult.status === "unprocessed") {
          const errorMessages = applyResult.errors
            .map((err: any) => getShopifyErrorMessage(err.code))
            .join(", ");
          throw new Error(`Failed to add product: ${errorMessages}`);
        }

        // Track successful add to order
        if (shopDomain && sessionId) {
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
        console.log(`Apollo: Product ${product.id} added successfully`);

        // Auto-continue after adding to order
        await done();
      } catch (error) {
        console.error("Apollo: Error adding product:", error);
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

  // Calculate price breakdown
  const itemPrice = currentVariant ? currentVariant.price * currentQuantity : 0;
  const shipping = 5.0;
  const tax = itemPrice * 0.18;
  const subtotal = itemPrice;
  const total = subtotal + shipping + tax;

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
          { viewportSize: "small", sizes: [1, 30, 1] },
          { viewportSize: "medium", sizes: [300, 30, 0.5] },
          { viewportSize: "large", sizes: [400, 30, 0.33] },
        ]}
      >
        {/* Product Image */}
        {/* @ts-ignore */}
        <View>
          {/* @ts-ignore */}
          <Image
            source={product.image?.url || ""}
            description={product.title}
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
                      options={option.values.map((value: string) => ({
                        value: value,
                        label: value,
                        disabled: !availableValues.includes(value),
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
                      {formatPrice(subtotal, currentVariant.currency_code)}
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
                      {formatPrice(shipping, currentVariant.currency_code)}
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
                    <Text alignment="end">
                      {formatPrice(tax, currentVariant.currency_code)}
                    </Text>
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
                      {formatPrice(total, currentVariant.currency_code)}
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
              : `Pay now · ${currentVariant ? formatPrice(total, currentVariant.currency_code) : ""}`}
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
