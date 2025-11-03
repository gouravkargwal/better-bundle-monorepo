import { QuantitySelector } from "./QuantitySelector.jsx";
import { ProductOptions } from "./ProductOptions.jsx";
import { ProductImageGallery } from "./ProductImageGallery.jsx";
import {
  getProductImages,
  getAvailableOptions,
  getPrimaryImageUrl,
  getSelectedVariant,
  hasValidVariantSelected,
  isVariantInStock,
} from "../utils/productUtils.js";

/**
 * Main product card component
 */
export function ProductCard({
  product,
  index,
  selectedVariants,
  quantities,
  selectedImageIndex,
  expandedGalleries,
  adding,
  onOptionChange,
  onQuantityChange,
  onImageSelect,
  onGalleryToggle,
  onAddToCart,
}) {
  const images = getProductImages(product);
  const hasMultipleImages = images.length > 1;
  const availableOptions = getAvailableOptions(
    product,
    selectedVariants[product.id] || {},
  );
  const primaryImageUrl = getPrimaryImageUrl(product, selectedImageIndex);
  const quantity = quantities[product.id] || 1;
  const isAdding = adding[product.id] || false;

  console.log(
    "🖼️ Rendering product:",
    product.title,
    "Primary URL:",
    primaryImageUrl,
    "Images count:",
    images.length,
  );

  const handleAddToCart = () => {
    const variantId = getSelectedVariant(product, selectedVariants);
    onAddToCart(variantId, product.id, index);
  };

  const handleGalleryToggle = (e) => {
    if (!e || !e.currentTarget) return;
    const isOpen = "open" in e.currentTarget ? e.currentTarget.open : false;
    console.log(`Gallery ${isOpen ? "opened" : "closed"} for:`, product.title);
    onGalleryToggle(product.id, isOpen);
  };

  return (
    <s-stack direction="block" gap="small-200">
      {/* 🎯 MAIN PRODUCT CARD */}
      <s-box
        padding="base"
        border="base"
        borderRadius="base"
        borderWidth="base"
      >
        <s-stack direction="block" gap="small-200">
          {/* PRODUCT IMAGE - Landscape */}
          {primaryImageUrl && (
            <s-image
              src={primaryImageUrl}
              alt={product.title}
              aspectRatio="16/9"
              borderRadius="base"
              objectFit="cover"
            />
          )}

          {/* ROW 1: Title and Price */}
          <s-stack direction="inline" justifyContent="space-between">
            <s-text>{product.title}</s-text>
            <s-text type="strong">{product.price}</s-text>
          </s-stack>

          {/* ROW 2: Options (full width) */}
          <ProductOptions
            options={availableOptions}
            productId={product.id}
            selectedOptions={selectedVariants[product.id] || {}}
            onOptionChange={onOptionChange}
          />

          {/* ROW 3: Quantity and Cart Button (inline, cart button fills remaining space) */}
          <s-stack
            direction="inline"
            gap="base"
            alignItems="center"
            inlineSize="100%"
          >
            <QuantitySelector
              productId={product.id}
              quantity={quantity}
              onDecrement={() => onQuantityChange(product.id, quantity - 1)}
              onIncrement={() => onQuantityChange(product.id, quantity + 1)}
              disabled={isAdding}
            />
            <s-button
              onClick={handleAddToCart}
              loading={isAdding}
              disabled={
                isAdding ||
                !hasValidVariantSelected(product, selectedVariants) ||
                !isVariantInStock(product, selectedVariants)
              }
              variant="primary"
              inlineSize="fit-content"
            >
              <s-icon type="cart" />
            </s-button>
          </s-stack>

          {/* 🎯 COLLAPSIBLE IMAGE GALLERY */}
          {hasMultipleImages && (
            <ProductImageGallery
              product={product}
              images={images}
              selectedImageIndex={selectedImageIndex}
              expanded={expandedGalleries?.[product.id] || false}
              onImageSelect={onImageSelect}
              onToggle={handleGalleryToggle}
            />
          )}
        </s-stack>
      </s-box>
    </s-stack>
  );
}
