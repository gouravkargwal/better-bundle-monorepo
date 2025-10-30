import type { FunctionalComponent } from "preact";
import { useState, useMemo, useEffect } from "preact/hooks";
import type { Product, Variant } from "../types";
import { formatPrice } from "../utils/format";
import styles from "../styles/carousel.module.css";

interface ProductCardProps {
  product: Product;
  position: number;
  currency: string;
  onClick: (
    productId: string | number,
    position: number,
    productUrl: string,
  ) => void;
  onAddToCart: (
    productId: string | number,
    variantId: string | number,
    position: number,
  ) => Promise<void>;
}

export const ProductCard: FunctionalComponent<ProductCardProps> = ({
  product,
  position,
  currency,
  onClick,
  onAddToCart,
}) => {
  const [qty, setQty] = useState(1);
  const [currentImage, setCurrentImage] = useState(product.image);
  const [isLoading, setIsLoading] = useState(false);

  // Initialize selected options immediately
  const [selectedOptions, setSelectedOptions] = useState<
    Record<string, string>
  >(() => {
    if (product.options?.length && product.variants.length) {
      const firstAvailableVariant =
        product.variants.find((v) => v.available) || product.variants[0];
      const initial: Record<string, string> = {};

      product.options.forEach((opt, idx) => {
        const optionKey = `option${idx + 1}` as keyof Variant;
        const value = firstAvailableVariant[optionKey];
        if (value) {
          initial[opt.name] = String(value);
        }
      });

      return initial;
    }
    return {};
  });

  // Find selected variant
  const selectedVariant = useMemo(() => {
    if (!product.options?.length) {
      return product.variants?.[0];
    }

    return product.variants?.find((v) => {
      return product.options!.every((opt, idx) => {
        const optionKey = `option${idx + 1}` as keyof Variant;
        return String(v[optionKey]) === selectedOptions[opt.name];
      });
    });
  }, [product.variants, product.options, selectedOptions]);

  // Update image when variant changes
  useEffect(() => {
    if (selectedVariant?.image) {
      setCurrentImage(selectedVariant.image);
    }
  }, [selectedVariant]);

  const handleOptionChange = (optionName: string, value: string) => {
    setSelectedOptions((prev) => ({
      ...prev,
      [optionName]: value,
    }));
  };

  const handleAddToCart = async () => {
    if (!selectedVariant || isLoading) return;
    setIsLoading(true);

    try {
      await onAddToCart(product.id, selectedVariant.variant_id, position);
    } finally {
      setIsLoading(false);
    }
  };

  const hasDiscount =
    selectedVariant?.compare_at_price &&
    selectedVariant.compare_at_price > (selectedVariant.price || product.price);

  return (
    <article className={styles.productCard} data-product-id={product.id}>
      {/* Image Section */}
      <div className={styles.imageSection}>
        <div
          className={styles.productImage}
          onClick={() => onClick(product.id, position, product.url)}
          role="button"
          tabIndex={0}
        >
          <img src={currentImage} alt={product.title} loading="lazy" />
          {hasDiscount && (
            <span className={styles.discountBadge}>
              {Math.round(
                ((selectedVariant.compare_at_price! -
                  (selectedVariant.price || product.price)) /
                  selectedVariant.compare_at_price!) *
                  100,
              )}
              % OFF
            </span>
          )}
        </div>
      </div>

      {/* Content Section */}
      <div className={styles.contentSection}>
        <h3 className={styles.productTitle}>{product.title}</h3>

        {/* Updated Price Section */}
        <div className={styles.priceSection}>
          <div className={styles.priceGroup}>
            <span className={styles.currentPrice}>
              {formatPrice(selectedVariant?.price ?? product.price, currency)}
            </span>
            {hasDiscount && (
              <span className={styles.originalPrice}>
                {formatPrice(selectedVariant.compare_at_price!, currency)}
              </span>
            )}
            {hasDiscount && (
              <span className={styles.discountPercent}>
                {Math.round(
                  ((selectedVariant.compare_at_price! -
                    (selectedVariant.price || product.price)) /
                    selectedVariant.compare_at_price!) *
                    100,
                )}
                % off
              </span>
            )}
          </div>

          <div className={styles.qtyGroup}>
            <span className={styles.qtyLabel}>Qty</span>
            <div className={styles.qtyControls}>
              <button
                className={styles.qtyBtn}
                onClick={() => setQty(Math.max(1, qty - 1))}
                disabled={qty <= 1}
              >
                −
              </button>
              <span className={styles.qtyValue}>{qty}</span>
              <button className={styles.qtyBtn} onClick={() => setQty(qty + 1)}>
                +
              </button>
            </div>
          </div>
        </div>

        {/* Variants - No Labels */}
        {product.options?.length ? (
          <div className={styles.variantsRow}>
            {product.options.map((option) => (
              <select
                key={option.name}
                className={styles.variantSelect}
                value={selectedOptions[option.name] || ""}
                onChange={(e) =>
                  handleOptionChange(option.name, e.currentTarget.value)
                }
              >
                {option.values.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            ))}
          </div>
        ) : null}

        {/* Add to Cart */}
        <button
          className={`${styles.addToCartBtn} ${isLoading ? styles.loading : ""} ${!selectedVariant?.available ? styles.disabled : ""}`}
          disabled={!selectedVariant?.available || isLoading}
          onClick={handleAddToCart}
        >
          {isLoading ? (
            <span className={styles.spinner}></span>
          ) : selectedVariant?.available ? (
            "Add to Cart"
          ) : (
            "Out of Stock"
          )}
        </button>
      </div>
    </article>
  );
};
