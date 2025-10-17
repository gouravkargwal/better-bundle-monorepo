import { render } from "preact";
import { useState, useEffect, useMemo, useRef } from "preact/hooks";
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
  const [adding, setAdding] = useState({});
  const [selectedVariants, setSelectedVariants] = useState({});
  const [quantities, setQuantities] = useState({});
  const [addedProducts, setAddedProducts] = useState(new Set());
  const hasTrackedView = useRef(false);

  // Get checkout data
  const { lines, cost, buyerIdentity, storage } = shopify;
  console.log("lines", lines);
  console.log("cost", cost);
  console.log("buyerIdentity", buyerIdentity);
  console.log("storage", storage);
  
  const shopDomain = shopify.shop.myshopifyDomain;
  const customerId = buyerIdentity?.customer?.value?.id || null;

  // Get cart data for context - memoized to prevent infinite re-renders
  const cartItems = useMemo(() => {
    return lines.value?.map(line => line.merchandise?.product?.id).filter(Boolean) || [];
  }, [lines.value]);
  
  const cartValue = useMemo(() => {
    return parseFloat(cost.totalAmount?.amount || "0");
  }, [cost.totalAmount?.amount]);

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

  // Track product views when loaded (only once)
  useEffect(() => {
    if (products && products.length > 0 && !loading && !hasTrackedView.current) {
      hasTrackedView.current = true;
      trackRecommendationView();
    }
  }, [products, loading, trackRecommendationView]);

  async function handleAddToCart(variantId, productId, position) {
    try {
      // Set loading state for this specific product
      setAdding(prev => ({ ...prev, [productId]: true }));
      
      // Check if variantId is valid
      if (!variantId) {
        console.error("❌ Mercury: No variant ID available for product", productId);
        return;
      }
      
      // Convert numeric ID to Shopify GID format
      const merchandiseId = variantId.startsWith('gid://') 
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
        
        // Mark product as added to prevent showing it again
        setAddedProducts(prev => new Set([...prev, productId]));
        
        // Track recommendation click only after successful add to cart
        await trackRecommendationClick(productId, position, null);
        await trackAddToCart(productId, position, variantId);
      } else {
        console.error("❌ Mercury: Failed to add product to cart");
      }
    } catch (err) {
      console.error("❌ Mercury: Error adding to cart:", err);
    } finally {
      // Clear loading state for this specific product
      setAdding(prev => ({ ...prev, [productId]: false }));
    }
  }


  function handleOptionChange(productId, optionName, optionValue) {
    setSelectedVariants(prev => {
      const current = prev[productId] || {};
      return {
        ...prev,
        [productId]: {
          ...current,
          [optionName]: optionValue
        }
      };
    });
  }

  function handleQuantityChange(productId, newQuantity) {
    setQuantities(prev => ({
      ...prev,
      [productId]: Math.max(1, Math.min(10, newQuantity)) // Limit between 1-10
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

  function getAvailableOptions(product, selectedOptions = {}) {
    if (!product.options || !product.variants) return product.options || [];

    return product.options.map(option => {
      const availableValues = new Set();
      
      // Find all variants that match currently selected options
      const matchingVariants = product.variants.filter(variant => {
        return Object.keys(selectedOptions).every(optionName => {
          if (optionName === option.name) return true; // Skip current option
          const selectedValue = selectedOptions[optionName];
          return variant.title && variant.title.includes(selectedValue);
        });
      });

      // Get available values for this option from matching variants
      matchingVariants.forEach(variant => {
        if (variant.inventory > 0) { // Only include in-stock variants
          const optionValue = getOptionValueFromVariant(variant, option.name, product);
          if (optionValue) {
            availableValues.add(optionValue);
          }
        }
      });

      return {
        ...option,
        values: option.values.filter(value => availableValues.has(value))
      };
    });
  }

  function getOptionValueFromVariant(variant, optionName, product) {
    // Find the option in the product options to get its position
    const option = product.options?.find(opt => opt.name === optionName);
    if (!option) return null;
    
    // Extract option value from variant title based on option position
    const title = variant.title || '';
    const parts = title.split(' / ');
    
    // Use the option position to determine which part of the title to extract
    const optionIndex = option.position - 1; // position is 1-based
    return parts[optionIndex] || null;
  }

  function getSelectedVariant(product) {
    const selected = selectedVariants[product.id];
    if (!selected || !product.variants) {
      return product.selectedVariantId || 
        (product.variants && product.variants.length > 0 ? product.variants[0].id : null);
    }

    // Find variant that matches all selected options
    const matchingVariant = product.variants.find(variant => {
      return Object.keys(selected).every(optionName => {
        const optionValue = selected[optionName];
        return variant.title && variant.title.includes(optionValue);
      });
    });

    return matchingVariant ? matchingVariant.id : product.selectedVariantId;
  }

  function isVariantInStock(product) {
    const selectedVariantId = getSelectedVariant(product);
    if (!selectedVariantId || !product.variants) return true;

    const variant = product.variants.find(v => v.id === selectedVariantId);
    return variant ? variant.inventory > 0 : true;
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
        <s-stack direction="block" spacing="base">
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

  // Filter out products that have been added to cart
  const availableProducts = products?.filter(product => !addedProducts.has(product.id)) || [];

  // Don't render if no products
  if (availableProducts.length === 0) {
    return null;
  }

  // Render recommendations - Order Summary Style
  return (
    <s-section heading="Recommended for you">
      <s-stack direction="block"  rowGap="large-200">
        {availableProducts.map((product, index) => (
          <s-box key={product.id} padding="none">
            {/* Main Product Layout - Horizontal like Order Summary */}
            <s-stack direction="inline" block-alignment="start" gap="base large-100">
              {/* Product Thumbnail - Fixed Width on Left (64px like order summary) */}
              <s-box min-inline-size="64px" max-inline-size="64px" >
                {product.image?.url ? (
                  <s-product-thumbnail
                    src={product.image.url}
                    alt={product.title}
                  ></s-product-thumbnail>
                ) : (
                  <s-box 
                    border="base" 
                    border-radius="base"
                    padding="base"
                  >
                    <s-text>No Image</s-text>
                  </s-box>
                )}
              </s-box>

              {/* Product Details - Flexible Width on Right */}
              <s-box>
                <s-stack direction="block" gap="base small-100">
                  {/* Product Title and Price */}
                  <s-stack direction="inline" justifyContent="space-between" >
                    <s-text>
                      {product.title}
                    </s-text>
                    <s-text>
                      {product.price}
                    </s-text>
                  </s-stack>

                  {/* Option Selects - Compact */}
                  {product.options && product.options.length > 0 && (
                    <s-stack direction="inline" justifyContent="space-between" gap="base large-300">
                      {getAvailableOptions(product, selectedVariants[product.id] || {}).map((option) => (
                        <s-select
                          key={option.id}
                          label={option.name}
                          value={selectedVariants[product.id]?.[option.name] || ''}
                          onChange={(e) => handleOptionChange(product.id, option.name, e.target.value || '')}

                        >
                          <s-option value="" >Select {option.name}</s-option>
                          {option.values.map((value) => (
                            <s-option key={value} value={value} >
                              {value}
                            </s-option>
                          ))}
                        </s-select>
                      ))}
                    </s-stack>
                  )}

                  {/* Out of Stock Warning */}
                  {!isVariantInStock(product) && (
                    <s-banner tone="critical">
                      Selected combination is out of stock
                    </s-banner>
                  )}

                  {/* Quantity and Add to Cart - Inline */}
                  <s-stack direction="inline" block-alignment="center" gap="base large-300" >
                    {/* Quantity Controls - Using Buttons */}
                    <s-stack direction="inline" block-alignment="center" alignItems="center" gap="base small-100" >
                      <s-button
                        onClick={(e) => {
                          e.stopPropagation();
                          decrementQuantity(product.id);
                        }}
                        disabled={adding[product.id] || getQuantity(product.id) <= 1}
                      >
                        -
                      </s-button>
                      
                      <s-text>
                        {getQuantity(product.id)}
                      </s-text>
                      
                      <s-button
                        onClick={(e) => {
                          e.stopPropagation();
                          incrementQuantity(product.id);
                        }}
                        disabled={adding[product.id] || getQuantity(product.id) >= 10}

                      >
                        +
                      </s-button>
                    </s-stack>

                    {/* Add to Cart Button */}
                    <s-button
                      onClick={(e) => {
                        e.stopPropagation();
                        const variantId = getSelectedVariant(product);
                        handleAddToCart(variantId, product.id, index);
                      }}
                      loading={adding[product.id] || false}
                      disabled={adding[product.id] || !isVariantInStock(product)}
                    >
                      {!isVariantInStock(product) 
                        ? 'Out of Stock' 
                        : 'Add to order'
                      }
                    </s-button>
                  </s-stack>
                </s-stack>
              </s-box>
            </s-stack>

          </s-box>
        ))}
      </s-stack>
    </s-section>
  );
}
