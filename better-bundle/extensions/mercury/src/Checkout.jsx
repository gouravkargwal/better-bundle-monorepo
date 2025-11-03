import { render } from "preact";
import { useState, useEffect, useMemo, useRef } from "preact/hooks";
import { useRecommendations } from "./hooks/useRecommendations.js";
import { trackAddToCart, getOrCreateSession } from "./api/analytics.js";
import { ProductCard } from "./components/ProductCard.jsx";
import { getOptionValueFromVariant } from "./utils/productUtils.js";
import { logger } from "./utils/logger.js";

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

  // Auto-select default variants when products load
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
    const t = setTimeout(() => {
      setSuccessMessage("");
    }, 5000); // Increased to 5 seconds for better visibility
    return () => clearTimeout(t);
  }, [successMessage]);

  async function handleAddToCart(variantId, productId, position) {
    try {
      setAdding((prev) => ({ ...prev, [productId]: true }));

      if (!variantId) {
        return;
      }

      const merchandiseId = variantId.startsWith("gid://")
        ? variantId
        : `gid://shopify/ProductVariant/${variantId}`;

      const quantity = quantities[productId] || 1;

      const result = await shopify.applyCartLinesChange({
        type: "addCartLine",
        merchandiseId: merchandiseId,
        quantity: quantity,
      });

      if (result.type === "success") {
        setAddedProducts((prev) => new Set([...prev, productId]));
        // Find product name for the success message
        const product = products?.find((p) => p.id === productId);
        const productName = product?.title || "Product";
        setSuccessMessage(`${productName} added to cart successfully`);

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
      }
    } catch (err) {
      logger.error({
        msg: "Error adding to cart",
        error: err,
        productId: productId,
        variantId: variantId,
        position: position,
      });
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

  function handleImageSelect(productId, imageIndex) {
    setSelectedImageIndex((prev) => {
      if (!prev) prev = {};
      return {
        ...prev,
        [productId]: imageIndex,
      };
    });
  }

  function handleGalleryToggle(productId, isOpen) {
    setExpandedGalleries((prev) => {
      if (!prev) prev = {};
      return {
        ...prev,
        [productId]: isOpen,
      };
    });
  }

  if (!shopifyPlusValidated && !loading) {
    return null;
  }

  if (loading) {
    return (
      <s-section heading="Recommended for you">
        <s-stack direction="block" gap="base">
          {[1].map((i) => (
            <s-box
              key={i}
              padding="base"
              border="base"
              borderRadius="base"
              borderWidth="base"
            >
              <s-stack direction="block" gap="small-200">
                {/* Skeleton Image - Landscape */}
                <s-box background="subdued" borderRadius="base" padding="base">
                  <s-skeleton-paragraph content="Image"></s-skeleton-paragraph>
                </s-box>

                {/* Skeleton Title and Price - Inline */}
                <s-stack direction="inline" justifyContent="space-between">
                  <s-skeleton-paragraph content="Product Title"></s-skeleton-paragraph>
                  <s-skeleton-paragraph content="$99.99"></s-skeleton-paragraph>
                </s-stack>

                {/* Skeleton Options - Inline */}
                <s-stack direction="inline" gap="small-200">
                  <s-box inlineSize="48%" minInlineSize="0">
                    <s-skeleton-paragraph content="Option 1"></s-skeleton-paragraph>
                  </s-box>
                  <s-box inlineSize="48%" minInlineSize="0">
                    <s-skeleton-paragraph content="Option 2"></s-skeleton-paragraph>
                  </s-box>
                </s-stack>

                {/* Skeleton Quantity and Button - Inline */}
                <s-stack
                  direction="inline"
                  gap="base"
                  alignItems="center"
                  justifyContent="space-between"
                >
                  <s-skeleton-paragraph content="Quantity"></s-skeleton-paragraph>
                  <s-box minInlineSize="0" inlineSize="60%">
                    <s-skeleton-paragraph content="Add to Cart"></s-skeleton-paragraph>
                  </s-box>
                </s-stack>
              </s-stack>
            </s-box>
          ))}
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

  if (!products || products.length === 0 || availableProducts.length === 0) {
    return null;
  }

  return (
    <s-section heading="Recommended for you">
      {successMessage && (
        <s-banner
          tone="success"
          dismissible
          onDismiss={() => {
            setSuccessMessage("");
          }}
        >
          <s-text type="strong">{successMessage}</s-text>
        </s-banner>
      )}

      <s-stack direction="block" gap="base">
        {availableProducts.map((product, index) => (
          <ProductCard
            key={product.id}
            product={product}
            index={index}
            selectedVariants={selectedVariants}
            quantities={quantities}
            selectedImageIndex={selectedImageIndex}
            expandedGalleries={expandedGalleries}
            adding={adding}
            onOptionChange={handleOptionChange}
            onQuantityChange={handleQuantityChange}
            onImageSelect={handleImageSelect}
            onGalleryToggle={handleGalleryToggle}
            onAddToCart={handleAddToCart}
          />
        ))}
      </s-stack>
    </s-section>
  );
}
