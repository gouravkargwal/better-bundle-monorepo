import { render } from "preact";
import { useState, useEffect, useMemo } from "preact/hooks";
import { useRecommendations } from "./hooks/useMercuryRecommendations.js";

// Track add to cart function
const trackAddToCart = async (productId, position, variantId) => {
  try {
    // Simple console log for now - analytics will be handled by the hook
    console.log("Mercury: Product added to cart", { productId, position, variantId });
  } catch (error) {
    console.error("Failed to track add to cart:", error);
  }
};

// Check if Shopify Plus is validated
const shopifyPlusValidated = shopify.instructions.value.attributes.canUpdateAttributes;

// 1. Export the extension
export default async () => {
  render(<Extension />, document.body)
};

function Extension() {
  const [adding, setAdding] = useState(false);

  // Get checkout data
  const { lines, cost, buyerIdentity, storage } = shopify;
  const shopDomain = shopify.shop.myshopifyDomain;
  const customerId = buyerIdentity?.customer?.id || null;

  // Get cart data for context - memoized to prevent infinite re-renders
  const cartItems = useMemo(() => {
    return lines.value?.map(line => line.merchandise?.product?.id).filter(Boolean) || [];
  }, [lines.value]);
  
  const cartValue = useMemo(() => {
    return parseFloat(cost.value?.totalAmount?.amount || "0");
  }, [cost.value?.totalAmount?.amount]);

  // Use Mercury recommendations hook with cart data
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
    // Pass cart data for better recommendations
    cartItems: cartItems,
    cartValue: cartValue,
    checkoutStep: "order_summary", // Current checkout step
  });

  // Track product views when loaded
  useEffect(() => {
    if (products && products.length > 0 && !loading) {
      trackRecommendationView();
    }
  }, [products, loading, trackRecommendationView]);

  async function handleAddToCart(variantId, productId, position) {
    try {
      setAdding(true);
      
      await trackAddToCart(productId, position, variantId);
      
      const result = await shopify.applyCartLinesChange({
        type: "addCartLine",
        merchandiseId: variantId,
        quantity: 1,
      });
      
      if (result.type === "success") {
        console.log("✅ Mercury: Product added to cart");
      } else {
        console.error("❌ Mercury: Failed to add product to cart");
      }
    } catch (err) {
      console.error("❌ Mercury: Error adding to cart:", err);
    } finally {
      setAdding(false);
    }
  }

  async function handleProductClick(productId, position, productUrl) {
    await trackRecommendationClick(productId, position, productUrl);
  }

  // Check feature availability
  if (!shopify.instructions.value.attributes.canUpdateAttributes) {
    return (
      <s-banner heading="Mercury" tone="warning">
        {shopify.i18n.translate("attributeChangesAreNotSupported")}
      </s-banner>
    );
  }

  // Don't render if not Shopify Plus
  if (!shopifyPlusValidated && !loading) {
    return null;
  }

  // Show loading state
  if (loading) {
    return (
      <s-section heading="Recommended for you">
        <s-stack>
          <s-skeleton-paragraph></s-skeleton-paragraph>
          <s-skeleton-paragraph></s-skeleton-paragraph>
          <s-skeleton-paragraph></s-skeleton-paragraph>
        </s-stack>
      </s-section>
    );
  }

  // Show error state
  if (error) {
    return null; // Silent fail for better UX
  }

  // Don't render if no products
  if (!products || products.length === 0) {
    return null;
  }

  // Render recommendations
  return (
    <s-section heading="Recommended for you">
      <s-stack>
        {products.map((product, index) => (
          <s-clickable
            key={product.id}
            onClick={() => handleProductClick(product.id, index, product.url)}
          >
            <s-box border="base" padding="base" borderRadius="base">
              <s-stack>
                {product.image?.url && (
                  <s-image
                    src={product.image.url}
                    alt={product.title}
                    aspectRatio="1/1"
                  />
                )}
                
                <s-stack>
                  <s-text>
                    {product.title}
                  </s-text>
                  
                  <s-text>
                    {product.price}
                  </s-text>
                </s-stack>

                <s-button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleAddToCart(product.variant_id, product.id, index);
                  }}
                  loading={adding}
                  disabled={adding}
                >
                  Add to cart
                </s-button>
              </s-stack>
            </s-box>
          </s-clickable>
        ))}
      </s-stack>
    </s-section>
  );
}
