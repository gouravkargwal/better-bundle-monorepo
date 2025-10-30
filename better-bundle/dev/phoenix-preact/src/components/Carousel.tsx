import type { FunctionalComponent } from "preact";
import { useEffect, useRef, useMemo } from "preact/hooks";
import { Splide } from "@splidejs/splide";
import "@splidejs/splide/css/core";
import { ProductCard } from "./ProductCard";
import { useRecommendations } from "../hooks/useRecommendations";
import type { Product } from "../types";
import type { ExtensionContext } from "../api/analytics";
import styles from "../styles/carousel.module.css";

interface CarouselProps {
  productIds: (string | number)[];
  customerId?: string;
  shopDomain: string;
  limit: number;
  context: ExtensionContext;
  enableAutoplay: boolean;
  autoplayDelay: number;
  showArrows: boolean;
  showPagination: boolean;
  currency: string;
}

export const Carousel: FunctionalComponent<CarouselProps> = ({
  productIds,
  customerId,
  shopDomain,
  limit,
  context,
  enableAutoplay,
  autoplayDelay,
  showArrows,
  showPagination,
  currency,
}) => {
  const splideRef = useRef<HTMLDivElement>(null);
  const splideInstance = useRef<Splide | null>(null);

  const {
    products: hookProducts,
    error,
    isDesignMode,
    trackRecommendationClick,
    trackRecommendationView,
  } = useRecommendations({
    context,
    limit,
    customerId: customerId || "",
    shopDomain,
    currency,
  });

  // Transform hook products to Product format
  const products = useMemo<Product[] | null>(() => {
    if (!hookProducts) return null;

    return hookProducts.map((p) => {
      const priceMatch = p.price.match(/[\d.]+/);
      const price = priceMatch ? parseFloat(priceMatch[0]) : 0;

      const rawProduct = p as any;
      const apiOptions = rawProduct.options || [];
      const apiVariants = rawProduct.variants || [];

      const transformedVariants = apiVariants.map((v: any) => {
        const titleParts = v.title?.split(" / ") || [];
        const variantOptions: Record<string, string> = {};

        apiOptions.forEach((opt: any, idx: number) => {
          const optionKey = `option${idx + 1}`;
          variantOptions[optionKey] = titleParts[idx] || "";
        });

        return {
          variant_id: v.variant_id || v.variantId,
          title: v.title || "",
          price:
            typeof v.price === "number"
              ? v.price
              : parseFloat(String(v.price || "0")),
          compare_at_price: v.compare_at_price ?? null,
          available: (v.inventory ?? 0) > 0,
          inventory: v.inventory ?? null,
          option1: variantOptions.option1 || null,
          option2: variantOptions.option2 || null,
          option3: variantOptions.option3 || null,
          image: v.image || null,
        };
      });

      const transformedOptions = apiOptions.map((opt: any) => ({
        name: opt.name || "",
        values: opt.values || [],
      }));

      return {
        id: p.id,
        title: p.title,
        image: p.image?.url || "",
        url: p.url || "#",
        price,
        compare_at_price: transformedVariants[0]?.compare_at_price ?? null,
        currency,
        variants: transformedVariants,
        options: transformedOptions.length > 0 ? transformedOptions : undefined,
        images: p.images?.map((img) => img.url) || [],
      };
    });
  }, [hookProducts, currency]);

  // Track view when products load
  useEffect(() => {
    if (products && products.length > 0 && !isDesignMode) {
      trackRecommendationView();
    }
  }, [products, isDesignMode, trackRecommendationView]);

  // Initialize Splide with custom pagination
  useEffect(() => {
    if (!products?.length || !splideRef.current || splideInstance.current)
      return;

    splideInstance.current = new Splide(splideRef.current, {
      type: products.length > 4 ? "loop" : "slide",
      perPage: 4,
      perMove: 1,
      gap: "0.5rem", // Reduced gap
      arrows: false, // We'll use custom arrows
      pagination: false, // We'll use custom pagination
      autoplay: enableAutoplay,
      interval: autoplayDelay,
      pauseOnHover: true,
      pauseOnFocus: true,
      breakpoints: {
        1200: { perPage: 3 },
        768: { perPage: 2 },
        480: { perPage: 1 },
      },
      lazyLoad: "nearby",
      preloadPages: 1,
    });

    splideInstance.current.mount();

    return () => {
      if (splideInstance.current) {
        splideInstance.current.destroy();
        splideInstance.current = null;
      }
    };
  }, [products, enableAutoplay, autoplayDelay]);

  // Custom navigation handlers
  const handlePrev = () => {
    if (splideInstance.current) {
      splideInstance.current.go("<");
    }
  };

  const handleNext = () => {
    if (splideInstance.current) {
      splideInstance.current.go(">");
    }
  };

  const handleClick = async (
    productId: string | number,
    position: number,
    productUrl: string,
  ) => {
    if (isDesignMode) return;
    const url = await trackRecommendationClick(
      String(productId),
      position,
      productUrl,
    );
    window.location.href = url;
  };

  const handleAddToCart = async (
    productId: string | number,
    variantId: string | number,
    position: number,
  ) => {
    if (isDesignMode) {
      alert("Add to cart works in live preview only");
      return;
    }

    try {
      const shopify = (window as any).Shopify;
      if (shopify?.analytics?.addToCart) {
        const props = {
          _bb_rec_product_id: String(productId),
          _bb_rec_extension: "phoenix",
          _bb_rec_context: context,
          _bb_rec_position: String(position),
          _bb_rec_timestamp: new Date().toISOString(),
          _bb_rec_source: "betterbundle",
        };
        await shopify.analytics.addToCart(variantId, 1, props);
        window.location.reload();
      } else {
        const product = products?.find((p) => p.id === productId);
        if (product) {
          window.location.href = product.url;
        }
      }
    } catch (error) {
      console.error("Failed to add to cart:", error);
    }
  };

  if (error) {
    return (
      <div className={styles.phoenixCarousel}>
        <div className={styles.error}>
          Failed to load recommendations: {error}
        </div>
      </div>
    );
  }

  if (!products) {
    return (
      <div className={styles.phoenixCarousel}>
        <div className={styles.loading}>Loading recommendations...</div>
      </div>
    );
  }

  if (products.length === 0) return null;

  // Calculate if we need pagination (more items than visible)
  const needsPagination = products.length > 4;

  return (
    <div className={styles.phoenixCarousel}>
      <div ref={splideRef} className="splide">
        <div className="splide__track">
          <ul className="splide__list">
            {products.map((product, idx) => (
              <li key={String(product.id)} className="splide__slide">
                <ProductCard
                  product={product}
                  position={idx + 1}
                  currency={currency}
                  onClick={handleClick}
                  onAddToCart={handleAddToCart}
                />
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Custom Pagination - Same style as product cards */}
      {needsPagination && (showArrows || showPagination) && (
        <div className={styles.carouselPagination}>
          {showArrows && (
            <button
              className={styles.carouselArrow}
              onClick={handlePrev}
              aria-label="Previous products"
            >
              ‹
            </button>
          )}

          {showPagination && (
            <div className={styles.carouselDots}>
              {/* We'll show simplified dots for main carousel */}
              <div className={styles.carouselDot} />
              <div className={styles.carouselDot} />
              <div className={styles.carouselDot} />
            </div>
          )}

          {showArrows && (
            <button
              className={styles.carouselArrow}
              onClick={handleNext}
              aria-label="Next products"
            >
              ›
            </button>
          )}
        </div>
      )}
    </div>
  );
};
