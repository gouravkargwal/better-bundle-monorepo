import { render } from "preact";
import { useState, useEffect, useMemo, useRef } from "preact/hooks";
import { useRecommendations } from "./hooks/useMercuryRecommendations.js";

const trackAddToCart = async (productId, position, variantId) => {
  try {
    console.log("Mercury: Product added to cart", {
      productId,
      position,
      variantId,
    });
  } catch (error) {
    console.error("Failed to track add to cart:", error);
  }
};

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
  const { lines, cost, buyerIdentity, storage } = shopify;
  const shopDomain = shopify.shop.myshopifyDomain;
  const customerId = buyerIdentity?.customer?.value?.id || null;

  const cartItems = useMemo(() => {
    return (
      lines.value
        ?.map((line) => line.merchandise?.product?.id)
        .filter(Boolean) || []
    );
  }, [lines.value]);

  const cartValue = useMemo(() => {
    const amount = cost.totalAmount?.value?.amount;
    return parseFloat(amount ? String(amount) : "0");
  }, [cost.totalAmount?.value?.amount]);

  const {
    loading,
    products,
    error,
    trackRecommendationClick,
    trackRecommendationView,
  } = useRecommendations({
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
        console.log("✅ Mercury: Product added to cart");
        setAddedProducts((prev) => new Set([...prev, productId]));
        await trackRecommendationClick(productId, position, null);
        await trackAddToCart(productId, position, variantId);
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
    const selected = selectedVariants[product.id];
    if (!selected || !product.variants) {
      return (
        product.selectedVariantId ||
        (product.variants && product.variants.length > 0
          ? product.variants[0].id
          : null)
      );
    }
    const matchingVariant = product.variants.find((variant) => {
      return Object.keys(selected).every((optionName) => {
        const optionValue = selected[optionName];
        return variant.title && variant.title.includes(optionValue);
      });
    });
    return matchingVariant ? matchingVariant.id : product.selectedVariantId;
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

  const availableProducts =
    products?.filter((product) => !addedProducts.has(product.id)) || [];

  if (availableProducts.length === 0) {
    return null;
  }

  return (
    <s-section heading="Recommended for you">
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
              minInlineSize="280px"
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
                      <s-stack direction="block" gap="small">
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
                        adding[product.id] || !isVariantInStock(product)
                      }
                    >
                      {!isVariantInStock(product)
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
