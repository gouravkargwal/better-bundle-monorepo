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
  const [successMessage, setSuccessMessage] = useState("");
  const hasTrackedView = useRef(false);
  const [selectedImageIndex, setSelectedImageIndex] = useState({});
  const [expandedGalleries, setExpandedGalleries] = useState({});
  const { lines, cost, buyerIdentity, storage } = shopify;
  const shopDomain = shopify.shop.myshopifyDomain;
  const customerId = buyerIdentity?.customer?.value?.id || null;

  const cartItems = useMemo(() => {
    return (
      lines.value
        ?.map((line) => {
          const productId = line.merchandise?.product?.id;
          if (!productId) return null;
          if (productId.startsWith("gid://shopify/Product/")) {
            return productId.split("/").pop();
          }
          return productId;
        })
        .filter(Boolean) || []
    );
  }, [lines.value]);

  useEffect(() => {
    const cartProductIds = new Set(cartItems);
    setAddedProducts((prev) => {
      const newSet = new Set();
      cartProductIds.forEach((id) => newSet.add(id));
      prev.forEach((id) => {
        if (!cartProductIds.has(id)) {
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

  useEffect(() => {
    if (products && products.length > 0) {
      products.forEach((product) => {
        if (selectedVariants[product.id]) return;

        if (product.options && product.options.length > 0) {
          const autoSelected = {};
          product.options.forEach((option) => {
            const firstAvailableVariant =
              product.variants?.find((variant) => variant.inventory > 0) ||
              product.variants?.[0];

            if (firstAvailableVariant && option.values.length > 0) {
              const optionValue = getOptionValueFromVariant(
                firstAvailableVariant,
                option.name,
                product,
              );
              autoSelected[option.name] = optionValue || option.values[0];
            } else if (option.values.length > 0) {
              autoSelected[option.name] = option.values[0];
            }
          });

          if (Object.keys(autoSelected).length > 0) {
            setSelectedVariants((prev) => {
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
  }, [products]);

  useEffect(() => {
    if (!successMessage) return;
    const t = setTimeout(() => setSuccessMessage(""), 3000);
    return () => clearTimeout(t);
  }, [successMessage]);

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
        setSuccessMessage("Added to cart successfully");

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

          const allAddedProducts = Array.from(addedProducts);
          const productsArray = allAddedProducts.map((addedProductId) => ({
            product_id: addedProductId,
            position: position,
            quantity: quantity,
            timestamp: new Date().toISOString(),
          }));

          if (!allAddedProducts.includes(productId)) {
            productsArray.push({
              product_id: productId,
              position: position,
              quantity: quantity,
              timestamp: new Date().toISOString(),
            });
          }

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
        }

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
    return selectedImageIndex?.[productId] ?? 0;
  }

  function getProductImages(product) {
    console.log("🔍 Product images for", product.title, ":", product);

    if (!product.images || product.images.length === 0) {
      if (product.image?.url) {
        console.log("✅ Using fallback image:", product.image.url);
        return [{ url: product.image.url }];
      }
      console.log("❌ No images found for product:", product.title);
      return [];
    }
    console.log(
      "✅ Using product images array:",
      product.images.length,
      "images",
    );
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

    if (!selected || Object.keys(selected).length === 0 || !product.variants) {
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

    const requiredOptions = product.options || [];
    const allOptionsSelected = requiredOptions.every((option) => {
      return selected[option.name] && selected[option.name] !== "";
    });

    if (!allOptionsSelected) {
      const firstAvailableVariant = product.variants?.find(
        (variant) => variant.inventory > 0,
      );
      return firstAvailableVariant
        ? firstAvailableVariant.id
        : product.variants && product.variants.length > 0
          ? product.variants[0].id
          : null;
    }

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

    const selected = selectedVariants[product.id] || {};
    const requiredOptions = product.options || [];
    const allOptionsSelected = requiredOptions.every((option) => {
      return selected[option.name] && selected[option.name] !== "";
    });

    return requiredOptions.length === 0 || allOptionsSelected;
  }

  function isVariantInStock(product) {
    const selectedVariantId = getSelectedVariant(product);
    if (!selectedVariantId || !product.variants) return true;
    const variant = product.variants.find((v) => v.id === selectedVariantId);
    return variant ? variant.inventory > 0 : true;
  }

  // Get the primary image URL safely
  function getPrimaryImageUrl(product) {
    const images = getProductImages(product);
    if (images.length === 0) {
      console.log("❌ No primary image URL for product:", product.title);
      return null;
    }

    const selectedIndex = getSelectedImageIndex(product.id);
    const selectedImage = images[selectedIndex];
    const fallbackImage = images[0];
    const imageUrl = selectedImage?.url || fallbackImage?.url || null;

    console.log("🖼️ Primary image URL for", product.title, ":", imageUrl);
    return imageUrl;
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
    console.error("❌ Error in useRecommendations:", error);
    return null;
  }

  const availableProducts =
    products?.filter((product) => {
      const productId = product.id;
      const numericId = productId.toString();
      const isInCart = cartItems.includes(numericId);
      const isRecentlyAdded = addedProducts.has(productId);
      return !isInCart && !isRecentlyAdded;
    }) || [];

  console.log("🛒 Available products:", availableProducts.length);

  if (!products || products.length === 0 || availableProducts.length === 0) {
    return null;
  }

  return (
    <s-section heading="Recommended for you">
      {successMessage && (
        <s-banner tone="success" dismissible>
          <s-text>{successMessage}</s-text>
        </s-banner>
      )}

      <s-stack direction="block" gap="base">
        {availableProducts.map((product, index) => {
          const images = getProductImages(product);
          const hasMultipleImages = images.length > 1;
          const availableOptions = getAvailableOptions(
            product,
            selectedVariants[product.id] || {},
          );
          const primaryImageUrl = getPrimaryImageUrl(product);

          console.log(
            "🖼️ Rendering product:",
            product.title,
            "Primary URL:",
            primaryImageUrl,
            "Images count:",
            images.length,
          );

          return (
            <s-stack key={product.id} direction="block" gap="small-200">
              {/* 🎯 MAIN PRODUCT CARD */}
              <s-box
                padding="base"
                border="base"
                borderRadius="base"
                borderWidth="base"
              >
                <s-stack direction="block" gap="small-200">
                  {/* TOP ROW: Image | Content */}
                  <s-stack direction="inline" gap="base" alignItems="start">
                    {/* LEFT SIDE: MAIN IMAGE */}
                    <s-box minInlineSize="80px">
                      {primaryImageUrl ? (
                        <s-box
                          background="subdued"
                          borderRadius="base"
                          padding="base"
                        >
                          <s-image
                            src={primaryImageUrl}
                            alt={product.title}
                            aspectRatio="1/1"
                            borderRadius="base"
                            objectFit="cover"
                          />
                        </s-box>
                      ) : (
                        <s-box
                          minInlineSize="80px"
                          minBlockSize="80px"
                          background="subdued"
                          borderRadius="base"
                          padding="base"
                        >
                          <s-text>No Image</s-text>
                        </s-box>
                      )}
                    </s-box>

                    {/* RIGHT SIDE: Content */}
                    <s-stack
                      direction="block"
                      gap="small-200"
                      inlineSize="auto"
                    >
                      {/* ROW 1: Title/Price | Quantity */}
                      <s-stack
                        direction="inline"
                        gap="base"
                        alignItems="center"
                        justifyContent="space-between"
                      >
                        <s-stack direction="block" gap="small-100">
                          <s-text>{product.title}</s-text>
                          <s-text type="strong">{product.price}</s-text>
                        </s-stack>

                        <s-stack
                          direction="inline"
                          gap="small-100"
                          alignItems="center"
                        >
                          <s-button
                            onClick={() => decrementQuantity(product.id)}
                            disabled={
                              adding[product.id] || getQuantity(product.id) <= 1
                            }
                          >
                            <s-icon type="minus" />
                          </s-button>
                          <s-text>{getQuantity(product.id)}</s-text>
                          <s-button
                            onClick={() => incrementQuantity(product.id)}
                            disabled={
                              adding[product.id] ||
                              getQuantity(product.id) >= 10
                            }
                          >
                            <s-icon type="plus" />
                          </s-button>
                        </s-stack>
                      </s-stack>

                      {/* ROW 2: Options | Cart Button */}
                      <s-stack
                        direction="inline"
                        gap="small-200"
                        alignItems="center"
                        justifyContent="space-between"
                      >
                        {availableOptions.length > 0 ? (
                          <s-stack direction="inline" gap="small-200">
                            {availableOptions.map((option) => (
                              <s-select
                                key={option.id}
                                label={option.name}
                                value={
                                  selectedVariants[product.id]?.[option.name] ||
                                  ""
                                }
                                onChange={(e) => {
                                  const value =
                                    e.currentTarget &&
                                    "value" in e.currentTarget
                                      ? e.currentTarget.value
                                      : "";
                                  handleOptionChange(
                                    product.id,
                                    option.name,
                                    value,
                                  );
                                }}
                              >
                                <s-option value="">Select</s-option>
                                {option.values.map((value) => (
                                  <s-option key={value} value={value}>
                                    {value}
                                  </s-option>
                                ))}
                              </s-select>
                            ))}
                          </s-stack>
                        ) : (
                          <s-box></s-box>
                        )}

                        <s-button
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
                          <s-icon type="cart" />
                        </s-button>
                      </s-stack>
                    </s-stack>
                  </s-stack>

                  {/* 🎯 COLLAPSIBLE IMAGE GALLERY using s-details */}
                  {hasMultipleImages && (
                    <s-details
                      open={expandedGalleries?.[product.id] || false}
                      onToggle={(e) => {
                        if (!e || !e.currentTarget) return;
                        const isOpen =
                          "open" in e.currentTarget
                            ? e.currentTarget.open
                            : false;
                        console.log(
                          `Gallery ${isOpen ? "opened" : "closed"} for:`,
                          product.title,
                        );
                        setExpandedGalleries((prev) => {
                          if (!prev) prev = {};
                          return {
                            ...prev,
                            [product.id]: isOpen,
                          };
                        });
                      }}
                    >
                      <s-summary>
                        <s-text>View all {images.length} images</s-text>
                      </s-summary>

                      {/* Gallery Content */}
                      <s-box
                        padding="base"
                        background="subdued"
                        borderRadius="base"
                      >
                        {/* Current Image */}
                        <s-box paddingBlockEnd="base">
                          <s-image
                            src={
                              images[getSelectedImageIndex(product.id)]?.url ||
                              ""
                            }
                            alt={`${product.title} - Image ${getSelectedImageIndex(product.id) + 1}`}
                            aspectRatio="4/3"
                            inlineSize="fill"
                            borderRadius="base"
                            objectFit="cover"
                          />
                        </s-box>

                        {/* Image Counter */}
                        <s-box paddingBlockEnd="base">
                          <s-text type="small" color="subdued">
                            {getSelectedImageIndex(product.id) + 1} of{" "}
                            {images.length}
                          </s-text>
                        </s-box>

                        {/* Thumbnails */}
                        <s-stack
                          direction="inline"
                          gap="small-100"
                          justifyContent="center"
                        >
                          {images.map((image, index) => (
                            <s-clickable
                              key={index}
                              onClick={() => {
                                setSelectedImageIndex((prev) => {
                                  if (!prev) prev = {};
                                  return {
                                    ...prev,
                                    [product.id]: index,
                                  };
                                });
                              }}
                              accessibilityLabel={`View image ${index + 1}`}
                            >
                              <s-box
                                inlineSize="50px"
                                blockSize="50px"
                                border={
                                  getSelectedImageIndex(product.id) === index
                                    ? "base"
                                    : "none"
                                }
                                borderWidth={
                                  getSelectedImageIndex(product.id) === index
                                    ? "base"
                                    : "none"
                                }
                                borderRadius="small"
                                overflow="hidden"
                                padding="none"
                              >
                                <s-image
                                  src={image.url || ""}
                                  alt={`Thumbnail ${index + 1}`}
                                  aspectRatio="1/1"
                                  objectFit="cover"
                                />
                              </s-box>
                            </s-clickable>
                          ))}
                        </s-stack>
                      </s-box>
                    </s-details>
                  )}
                </s-stack>
              </s-box>
            </s-stack>
          );
        })}
      </s-stack>
    </s-section>
  );
}
