import type { FunctionalComponent } from "preact";
import { useEffect, useRef, useMemo } from "preact/hooks";
import { Splide } from "@splidejs/splide";
import "@splidejs/splide/css/core"; // Only core styles
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

  // In Carousel.tsx - Add logic to hide pagination when not needed
  useEffect(() => {
    if (!products?.length || !splideRef.current || splideInstance.current)
      return;

    const shouldShowPagination = showPagination && products.length > 4; // Only show if more than 4 items

    splideInstance.current = new Splide(splideRef.current, {
      type: products.length > 4 ? "loop" : "slide",
      perPage: 4,
      perMove: 1,
      gap: "1rem",
      arrows: showArrows,
      pagination: shouldShowPagination, // Conditional pagination
      autoplay: enableAutoplay,
      interval: autoplayDelay,
      pauseOnHover: true,
      pauseOnFocus: true,
      arrowPath:
        "M15.5 0.932L11.2 5.312 12.612 6.724 20.68 -1.344 12.612 -9.412 11.2 -8 15.5 -3.62 0 -3.62 0 -1.38 15.5 0.932Z",
      breakpoints: {
        1200: { perPage: 3, pagination: showPagination && products.length > 3 },
        768: { perPage: 2, pagination: showPagination && products.length > 2 },
        480: { perPage: 1, pagination: showPagination && products.length > 1 },
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
  }, [products, showArrows, showPagination, enableAutoplay, autoplayDelay]);

  // Handlers
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
    </div>
  );
};
