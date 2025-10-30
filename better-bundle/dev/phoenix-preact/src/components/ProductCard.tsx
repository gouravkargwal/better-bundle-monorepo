import type { FunctionalComponent } from "preact";
import { useState, useMemo, useEffect, useRef } from "preact/hooks";
import type { Product, Variant } from "../types";
import { formatCurrency, formatPrice } from "../utils/format";
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
  const [isLoading, setIsLoading] = useState(false);
  const [currentImageIndex, setCurrentImageIndex] = useState(0);
  const [showImageGallery, setShowImageGallery] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const autoSlideRef = useRef<NodeJS.Timeout | null>(null);

  // Get all available images
  const allImages = useMemo(() => {
    const images = [product.image];
    if (product.images && product.images.length > 0) {
      const additionalImages = product.images.filter(
        (img) => img !== product.image,
      );
      images.push(...additionalImages);
    }
    return images.filter(Boolean);
  }, [product.image, product.images]);

  // Initialize selected options
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

  // Auto-slide for desktop hover (only when gallery is active)
  useEffect(() => {
    if (isHovered && showImageGallery && allImages.length > 1) {
      autoSlideRef.current = setInterval(() => {
        setCurrentImageIndex((prev) => (prev + 1) % allImages.length);
      }, 2000);
    } else {
      if (autoSlideRef.current) {
        clearInterval(autoSlideRef.current);
        autoSlideRef.current = null;
      }
    }

    return () => {
      if (autoSlideRef.current) {
        clearInterval(autoSlideRef.current);
      }
    };
  }, [isHovered, showImageGallery, allImages.length]);

  // Reset gallery when hover ends
  useEffect(() => {
    if (!isHovered && showImageGallery) {
      setShowImageGallery(false);
      setCurrentImageIndex(0);
    }
  }, [isHovered, showImageGallery]);

  const handleImageClick = () => {
    onClick(product.id, position, product.url);
  };

  const handleSeeMoreClick = (e: Event) => {
    e.stopPropagation();
    setShowImageGallery(true);
  };

  const handlePrevImage = (e: Event) => {
    e.stopPropagation();
    setCurrentImageIndex(
      (prev) => (prev - 1 + allImages.length) % allImages.length,
    );
  };

  const handleNextImage = (e: Event) => {
    e.stopPropagation();
    setCurrentImageIndex((prev) => (prev + 1) % allImages.length);
  };

  const handleImageDotClick = (index: number, e: Event) => {
    e.stopPropagation();
    setCurrentImageIndex(index);
  };

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

  const currentImage = allImages[currentImageIndex] || product.image;
  const hasMultipleImages = allImages.length > 1;

  return (
    <article className={styles.productCard} data-product-id={product.id}>
      {/* Image Section */}
      <div
        className={styles.imageSection}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <div
          className={styles.productImage}
          onClick={handleImageClick}
          role="button"
          tabIndex={0}
        >
          <img
            src={currentImage}
            alt={`${product.title} - ${currentImageIndex + 1}`}
            loading="lazy"
            className={styles.productImg}
          />

          {/* "See More" Button - Only show if multiple images and not in gallery mode */}
          {hasMultipleImages && !showImageGallery && (
            <button
              className={styles.seeMoreBtn}
              onClick={handleSeeMoreClick}
              aria-label="View more images"
            >
              +{allImages.length - 1} more
            </button>
          )}

          {/* Discount Badge */}
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

        {/* Pagination Controls - Only show when gallery is active */}
        {hasMultipleImages && showImageGallery && (
          <div className={styles.imagePagination}>
            <button
              className={styles.paginationArrow}
              onClick={handlePrevImage}
              aria-label="Previous image"
            >
              ‹
            </button>

            <div className={styles.paginationDots}>
              {allImages.map((_, index) => (
                <button
                  key={index}
                  className={`${styles.paginationDot} ${index === currentImageIndex ? styles.paginationDotActive : ""}`}
                  onClick={(e) => handleImageDotClick(index, e)}
                  aria-label={`View image ${index + 1}`}
                />
              ))}
            </div>

            <button
              className={styles.paginationArrow}
              onClick={handleNextImage}
              aria-label="Next image"
            >
              ›
            </button>
          </div>
        )}
      </div>

      {/* Content Section */}
      <div className={styles.contentSection}>
        <h3 className={styles.productTitle}>{product.title}</h3>

        <div className={styles.priceSection}>
          <div className={styles.priceGroup}>
            <span className={styles.currentPrice}>
              {formatCurrency(
                selectedVariant?.price ?? product.price,
                currency,
                {
                  showSymbol: true,
                },
              )}
            </span>
            {hasDiscount && (
              <span className={styles.originalPrice}>
                {formatCurrency(selectedVariant.compare_at_price!, currency, {
                  showSymbol: true,
                })}
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
