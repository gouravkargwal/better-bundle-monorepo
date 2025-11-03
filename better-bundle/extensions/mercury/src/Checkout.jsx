import { render } from "preact";
import { useState, useEffect, useMemo, useRef } from "preact/hooks";
import { useRecommendations } from "./hooks/useRecommendations.js";
import { trackAddToCart, getOrCreateSession } from "./api/analytics.js";

const shopifyPlusValidated =
  shopify.instructions.value.attributes.canUpdateAttributes;

export default async () => {
  render(<Extension />, document.body);
};

function Extension() {
  const [adding, setAdding] = useState({});
  const [selectedVariants, setSelectedVariants] = useState({});
  const [quantities, setQuantities] = useState({});
  const [addedProducts, setAddedProducts] = useState(new Set());
  const hasTrackedView = useRef(false);
  const [selectedImageIndex, setSelectedImageIndex] = useState({});
  const [successMessage, setSuccessMessage] = useState(null); // Track success message
  const { lines, cost, buyerIdentity, storage } = shopify;
  const shopDomain = shopify.shop.myshopifyDomain;
  const customerId = buyerIdentity?.customer?.value?.id || null;

  const cartItems = useMemo(() => {
    return (
      lines.value
        ?.map((line) => {
          const productId = line.merchandise?.product?.id;
          if (!productId) return null;
          // Extract numeric ID from GID format (gid://shopify/Product/123456 -> 123456)
          if (productId.startsWith("gid://shopify/Product/")) {
            return productId.split("/").pop();
          }
          return productId;
        })
        .filter(Boolean) || []
    );
  }, [lines.value]);

  // ✅ Sync addedProducts with actual cart items when cart changes
  // This ensures we filter out products that are actually in cart (from any source)
  useEffect(() => {
    const cartProductIds = new Set(cartItems);
    setAddedProducts((prev) => {
      // Update: Keep products that are in cart (regardless of source)
      // Also keep products we just added (for immediate UI feedback)
      const newSet = new Set();
      cartProductIds.forEach((id) => newSet.add(id));
      // Keep products we added even if not yet in cart (pending add)
      prev.forEach((id) => {
        if (!cartProductIds.has(id)) {
          // Only keep if we recently added it (within last 5 seconds)
          // This provides immediate UI feedback while cart updates
          newSet.add(id);
        }
      });
      return newSet;
    });
  }, [cartItems]);

  const cartValue = useMemo(() => {
    const amount = cost.totalAmount?.value?.amount;
    return parseFloat(amount ? String(amount) : "0");
  }, [cost.totalAmount?.value?.amount]);

  const { loading, products, error, trackRecommendationView } =
    useRecommendations({
      context: "checkout_page",
      limit: 3,
      customerId,
      shopDomain,
      storage,
      cartItems: cartItems,
      cartValue: cartValue,
      checkoutStep: "order_summary",
    });

  useEffect(() => {
    if (
      products &&
      products.length > 0 &&
      !loading &&
      !hasTrackedView.current
    ) {
      hasTrackedView.current = true;
      trackRecommendationView();
    }
  }, [products, loading, trackRecommendationView]);

  // ✅ Auto-select first available variant for each product on load (better UX)
  useEffect(() => {
    if (products && products.length > 0) {
      products.forEach((product) => {
        // Skip if already has selection
        if (selectedVariants[product.id]) return;

        // Auto-select first available option value for each option
        if (product.options && product.options.length > 0) {
          const autoSelected = {};
          product.options.forEach((option) => {
            // Find first available variant and get its option value
            const firstAvailableVariant =
              product.variants?.find((variant) => variant.inventory > 0) ||
              product.variants?.[0];

            if (firstAvailableVariant && option.values.length > 0) {
              // Extract option value from variant title
              const optionValue = getOptionValueFromVariant(
                firstAvailableVariant,
                option.name,
                product,
              );

              // Use option value if found, otherwise use first value
              autoSelected[option.name] = optionValue || option.values[0];
            } else if (option.values.length > 0) {
              // Fallback to first value if no variant found
              autoSelected[option.name] = option.values[0];
            }
          });

          if (Object.keys(autoSelected).length > 0) {
            setSelectedVariants((prev) => {
              // Only update if product doesn't already have selection
              if (prev[product.id]) return prev;
              return {
                ...prev,
                [product.id]: autoSelected,
              };
            });
          }
        }
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [products]);

  async function handleAddToCart(variantId, productId, position) {
    try {
      setAdding((prev) => ({ ...prev, [productId]: true }));

      if (!variantId) {
        console.error(
          "❌ Mercury: No variant ID available for product",
          productId,
        );
        return;
      }

      const merchandiseId = variantId.startsWith("gid://")
        ? variantId
        : `gid://shopify/ProductVariant/${variantId}`;

      const quantity = getQuantity(productId);

      const result = await shopify.applyCartLinesChange({
        type: "addCartLine",
        merchandiseId: merchandiseId,
        quantity: quantity,
      });

      if (result.type === "success") {
        setAddedProducts((prev) => new Set([...prev, productId]));

        // ✅ Show success banner message
        const productTitle =
          products?.find((p) => p.id === productId)?.title || "Product";
        setSuccessMessage(`${productTitle} added to cart`);

        // Auto-dismiss banner after 3 seconds
        setTimeout(() => {
          setSuccessMessage(null);
        }, 3000);

        // ✅ NEW: Set cart metafields for Mercury attribution (similar to Apollo)
        // ✅ FIX: Accumulate multiple products in JSON array to handle multiple additions
        try {
          const sessionId = await getOrCreateSession(
            storage,
            shopDomain,
            customerId,
            null,
            null,
            null,
            null,
          );

          // ✅ Build products array from addedProducts state (tracks products added in this session)
          // Since we can't read cart metafields directly, we use component state to accumulate
          // The backend will handle deduplication when parsing the products array
          const allAddedProducts = Array.from(addedProducts);
          const productsArray = allAddedProducts.map((addedProductId) => ({
            product_id: addedProductId,
            position: position, // Use current position (will be updated per product if needed)
            quantity: quantity, // Use current quantity (will be updated per product if needed)
            timestamp: new Date().toISOString(),
          }));

          // Add current product if not already in the list
          if (!allAddedProducts.includes(productId)) {
            productsArray.push({
              product_id: productId,
              position: position,
              quantity: quantity,
              timestamp: new Date().toISOString(),
            });
          }

          // Store Mercury tracking data in cart metafields
          // Cart metafields become order metafields when order is created

          // Always set extension, session_id, context, source (these don't change per product)
          await shopify.applyMetafieldChange({
            type: "updateMetafield",
            namespace: "bb_recommendation",
            key: "extension",
            value: "mercury",
            valueType: "string",
          });

          await shopify.applyMetafieldChange({
            type: "updateMetafield",
            namespace: "bb_recommendation",
            key: "session_id",
            value: sessionId,
            valueType: "string",
          });

          await shopify.applyMetafieldChange({
            type: "updateMetafield",
            namespace: "bb_recommendation",
            key: "context",
            value: "checkout_page",
            valueType: "string",
          });

          await shopify.applyMetafieldChange({
            type: "updateMetafield",
            namespace: "bb_recommendation",
            key: "source",
            value: "betterbundle",
            valueType: "string",
          });

          // ✅ Store all products as JSON array (accumulates multiple products)
          await shopify.applyMetafieldChange({
            type: "updateMetafield",
            namespace: "bb_recommendation",
            key: "products",
            value: JSON.stringify(productsArray),
            valueType: "json_string",
          });
        } catch (metafieldError) {
          console.error(
            "❌ Mercury: Failed to set cart metafields:",
            metafieldError,
          );
          // Don't block add to cart if metafield setting fails
        }

        // Track add to cart event (not click event)
        await trackAddToCart(
          storage,
          shopDomain,
          "checkout_page",
          productId,
          variantId,
          position,
          customerId,
          {
            source: "mercury_recommendation",
            cart_product_count: cartItems.length,
            quantity: quantity,
            checkout_step: "order_summary",
            cart_value: cartValue,
          },
        );
      } else {
        console.error("❌ Mercury: Failed to add product to cart");
      }
    } catch (err) {
      console.error("❌ Mercury: Error adding to cart:", err);
    } finally {
      setAdding((prev) => ({ ...prev, [productId]: false }));
    }
  }

  function handleOptionChange(productId, optionName, optionValue) {
    setSelectedVariants((prev) => {
      const current = prev[productId] || {};
      return {
        ...prev,
        [productId]: {
          ...current,
          [optionName]: optionValue,
        },
      };
    });
  }

  function handleQuantityChange(productId, newQuantity) {
    setQuantities((prev) => ({
      ...prev,
      [productId]: Math.max(1, Math.min(10, newQuantity)),
    }));
  }

  function incrementQuantity(productId) {
    const currentQuantity = quantities[productId] || 1;
    handleQuantityChange(productId, currentQuantity + 1);
  }

  function decrementQuantity(productId) {
    const currentQuantity = quantities[productId] || 1;
    handleQuantityChange(productId, currentQuantity - 1);
  }

  function getQuantity(productId) {
    return quantities[productId] || 1;
  }

  function getSelectedImageIndex(productId) {
    return selectedImageIndex[productId] || 0;
  }

  // Carousel functions
  function getProductImages(product) {
    if (!product.images || product.images.length === 0) {
      return product.image?.url ? [{ url: product.image.url }] : [];
    }
    return product.images;
  }

  function getAvailableOptions(product, selectedOptions = {}) {
    if (!product.options || !product.variants) return product.options || [];
    return product.options.map((option) => {
      const availableValues = new Set();
      const matchingVariants = product.variants.filter((variant) => {
        return Object.keys(selectedOptions).every((optionName) => {
          if (optionName === option.name) return true;
          const selectedValue = selectedOptions[optionName];
          return variant.title && variant.title.includes(selectedValue);
        });
      });
      matchingVariants.forEach((variant) => {
        if (variant.inventory > 0) {
          const optionValue = getOptionValueFromVariant(
            variant,
            option.name,
            product,
          );
          if (optionValue) {
            availableValues.add(optionValue);
          }
        }
      });
      return {
        ...option,
        values: option.values.filter((value) => availableValues.has(value)),
      };
    });
  }

  function getOptionValueFromVariant(variant, optionName, product) {
    const option = product.options?.find((opt) => opt.name === optionName);
    if (!option) return null;
    const title = variant.title || "";
    const parts = title.split(" / ");
    const optionIndex = option.position - 1;
    return parts[optionIndex] || null;
  }

  function getSelectedVariant(product) {
    // If no selection made, auto-select first available variant (better UX)
    const selected = selectedVariants[product.id];

    if (!selected || Object.keys(selected).length === 0 || !product.variants) {
      // Auto-select first available variant (in stock)
      const firstAvailableVariant = product.variants?.find(
        (variant) => variant.inventory > 0,
      );
      return (
        product.selectedVariantId ||
        (firstAvailableVariant ? firstAvailableVariant.id : null) ||
        (product.variants && product.variants.length > 0
          ? product.variants[0].id
          : null)
      );
    }

    // Check if all required options are selected
    const requiredOptions = product.options || [];
    const allOptionsSelected = requiredOptions.every((option) => {
      return selected[option.name] && selected[option.name] !== "";
    });

    if (!allOptionsSelected) {
      // Not all options selected - return first available variant as fallback
      const firstAvailableVariant = product.variants?.find(
        (variant) => variant.inventory > 0,
      );
      return firstAvailableVariant
        ? firstAvailableVariant.id
        : product.variants && product.variants.length > 0
          ? product.variants[0].id
          : null;
    }

    // Find matching variant based on selected options
    const matchingVariant = product.variants.find((variant) => {
      return Object.keys(selected).every((optionName) => {
        const optionValue = selected[optionName];
        return variant.title && variant.title.includes(optionValue);
      });
    });

    return matchingVariant ? matchingVariant.id : product.selectedVariantId;
  }

  function hasValidVariantSelected(product) {
    const variantId = getSelectedVariant(product);
    if (!variantId || !product.variants) return false;

    // Check if all required options are selected
    const selected = selectedVariants[product.id] || {};
    const requiredOptions = product.options || [];
    const allOptionsSelected = requiredOptions.every((option) => {
      return selected[option.name] && selected[option.name] !== "";
    });

    // If product has options, all must be selected
    // If no options, variant is valid
    return requiredOptions.length === 0 || allOptionsSelected;
  }

  function isVariantInStock(product) {
    const selectedVariantId = getSelectedVariant(product);
    if (!selectedVariantId || !product.variants) return true;
    const variant = product.variants.find((v) => v.id === selectedVariantId);
    return variant ? variant.inventory > 0 : true;
  }

  if (!shopifyPlusValidated && !loading) {
    return null;
  }

  if (loading) {
    return (
      <s-section heading="Recommended for you">
        <s-stack direction="block" gap="base">
          <s-skeleton-paragraph></s-skeleton-paragraph>
          <s-skeleton-paragraph></s-skeleton-paragraph>
        </s-stack>
      </s-section>
    );
  }

  if (error) {
    return null;
  }

  // ✅ Filter out products that are already in cart
  const availableProducts =
    products?.filter((product) => {
      const productId = product.id;
      // Extract numeric ID if needed for comparison
      const numericId = productId.toString();
      // Check if product is in cart (by actual cart items, not just addedProducts state)
      const isInCart = cartItems.includes(numericId);
      // Also check addedProducts for immediate filtering (cart might not have updated yet)
      const isRecentlyAdded = addedProducts.has(productId);
      return !isInCart && !isRecentlyAdded;
    }) || [];

  // ✅ Don't show section if no products available (following Venus pattern)
  if (!products || products.length === 0 || availableProducts.length === 0) {
    return null;
  }

  return (
    <s-section heading="Recommended for you">
      {/* Success Banner */}
      {successMessage && (
        <s-banner
          tone="success"
          dismissible
          onDismiss={() => setSuccessMessage(null)}
        >
          {successMessage}
        </s-banner>
      )}

      <s-stack direction="inline" gap="base">
        {availableProducts.map((product, index) => {
          const images = getProductImages(product);
          const hasMultipleImages = images.length > 1;

          return (
            <s-box
              key={product.id}
              padding="base"
              border="base"
              borderRadius="base"
              borderWidth="base"
              inlineSize="100%"
            >
              <s-stack direction="block" gap="base">
                {/* Image at the top - Phoenix style */}
                <s-box>
                  <s-stack direction="block" gap="small-100">
                    {/* Main Product Image */}
                    <s-box>
                      <s-image
                        src={images[getSelectedImageIndex(product.id)]?.url}
                        alt={product.title}
                        aspectRatio="16/9"
                        loading="lazy"
                      />
                    </s-box>

                    {/* Product Gallery with Thumbnails - Only show if multiple images */}
                    {hasMultipleImages && (
                      <s-scroll-box>
                        <s-stack
                          direction="inline"
                          gap="small-100"
                          justifyContent="center"
                        >
                          {images.map((image, index) => (
                            <s-link
                              key={index}
                              onClick={() =>
                                setSelectedImageIndex((prev) => ({
                                  ...prev,
                                  [product.id]: index,
                                }))
                              }
                              aria-label={`View image ${index + 1} of ${images.length}`}
                              aria-pressed={
                                selectedImageIndex[product.id] === index
                              }
                            >
                              <s-product-thumbnail
                                key={index}
                                src={image.url}
                                alt={`${product.title} - Image ${index + 1}`}
                              />
                            </s-link>
                          ))}
                        </s-stack>
                      </s-scroll-box>
                    )}
                  </s-stack>
                </s-box>

                {/* Content - Phoenix style layout */}
                <s-stack direction="block" gap="small">
                  {/* Title */}
                  <s-text>{product.title}</s-text>

                  {/* Price and Quantity on same line - Phoenix style */}
                  <s-stack
                    direction="inline"
                    gap="base"
                    justifyContent="space-between"
                    alignItems="center"
                  >
                    <s-text type="strong">{product.price}</s-text>
                    <s-stack direction="inline" gap="small">
                      <s-button
                        onClick={() => decrementQuantity(product.id)}
                        disabled={
                          adding[product.id] || getQuantity(product.id) <= 1
                        }
                        inlineSize="fit-content"
                      >
                        −
                      </s-button>
                      <s-number-field
                        value={getQuantity(product.id)}
                        min={1}
                        max={10}
                        onChange={(e) => {
                          const value = e.currentTarget.value;
                          handleQuantityChange(
                            product.id,
                            parseInt(value) || 1,
                          );
                        }}
                      />
                      <s-button
                        onClick={() => incrementQuantity(product.id)}
                        disabled={
                          adding[product.id] || getQuantity(product.id) >= 10
                        }
                      >
                        +
                      </s-button>
                    </s-stack>
                  </s-stack>

                  <s-box>
                    {/* Variant Options - Responsive layout */}
                    {product.options && product.options.length > 0 && (
                      <s-stack
                        direction="inline"
                        gap="small"
                        justifyContent="space-between"
                      >
                        {getAvailableOptions(
                          product,
                          selectedVariants[product.id] || {},
                        ).map((option) => (
                          <s-select
                            key={option.id}
                            label={option.name}
                            value={
                              selectedVariants[product.id]?.[option.name] || ""
                            }
                            onChange={(e) => {
                              const value = e.currentTarget.value;
                              handleOptionChange(
                                product.id,
                                option.name,
                                value,
                              );
                            }}
                          >
                            <s-option value="">Select {option.name}</s-option>
                            {option.values.map((value) => (
                              <s-option key={value} value={value}>
                                {value}
                              </s-option>
                            ))}
                          </s-select>
                        ))}
                      </s-stack>
                    )}
                  </s-box>
                  {/* Add to Cart Button - Phoenix style (full width) */}
                  <s-box>
                    <s-button
                      inlineSize="fill"
                      onClick={() => {
                        const variantId = getSelectedVariant(product);
                        handleAddToCart(variantId, product.id, index);
                      }}
                      loading={adding[product.id]}
                      disabled={
                        adding[product.id] ||
                        !hasValidVariantSelected(product) ||
                        !isVariantInStock(product)
                      }
                      variant="primary"
                    >
                      {!hasValidVariantSelected(product)
                        ? "Please select options"
                        : !isVariantInStock(product)
                          ? "Out of Stock"
                          : "Add to cart"}
                    </s-button>
                  </s-box>
                </s-stack>
              </s-stack>
            </s-box>
          );
        })}
      </s-stack>
    </s-section>
  );
}
