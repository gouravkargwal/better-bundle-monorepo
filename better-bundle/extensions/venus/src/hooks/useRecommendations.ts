import { useState, useEffect, useMemo } from "react";
import {
  recommendationApi,
  type ProductRecommendation,
} from "../api/recommendations";
import { analyticsApi, type ViewedProduct } from "../api/analytics";

interface Product {
  id: string;
  title: string;
  handle: string;
  price: string;
  image: string;
  inStock: boolean;
  url: string;
  variant_id?: string;
}

interface UseRecommendationsProps {
  context:
    | "profile"
    | "order_status"
    | "order_history"
    | "product_page"
    | "homepage"
    | "cart"
    | "checkout";
  limit: number;
  customerId: string;
  shopDomain?: string;
  columnConfig: {
    extraSmall: number;
    small: number;
    medium: number;
    large: number;
  };
}

export function useRecommendations({
  context,
  limit,
  customerId,
  shopDomain,
  columnConfig,
}: UseRecommendationsProps) {
  const [loading, setLoading] = useState(true);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(
    () =>
      `venus_${context}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
  );

  // Memoized column configuration
  const memoizedColumnConfig = useMemo(() => columnConfig, [columnConfig]);

  const trackRecommendationClick = async (
    productId: string,
    position: number,
    productUrl: string,
  ) => {
    try {
      await analyticsApi.trackInteraction({
        session_id: sessionId,
        product_id: productId,
        interaction_type: "click",
        position,
        extension_type: "venus",
        context,
        metadata: { source: `${context}_recommendation` },
      });

      // Add attribution parameters to track recommendation source
      const shortRef = sessionId
        .split("")
        .reduce((hash, char) => {
          return ((hash << 5) - hash + char.charCodeAt(0)) & 0xffffffff;
        }, 0)
        .toString(36)
        .substring(0, 6);

      const attributionParams = new URLSearchParams({
        ref: shortRef,
        src: productId,
        pos: position.toString(),
      });

      // Navigate to product page with attribution
      const productUrlWithAttribution = `${productUrl}?${attributionParams.toString()}`;
      console.log(
        `${context} recommendation clicked:`,
        productUrlWithAttribution,
      );
    } catch (error) {
      console.error(`Failed to track ${context} click:`, error);
    }
  };

  // Fetch recommendations
  useEffect(() => {
    const fetchRecommendations = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await recommendationApi.getRecommendations({
          context,
          limit,
          user_id: customerId,
          ...(shopDomain && { shop_domain: shopDomain }),
        });

        if (response.success && response.recommendations) {
          // Transform API response to component format
          const transformedProducts: Product[] = response.recommendations.map(
            (rec: ProductRecommendation) => ({
              id: rec.id,
              title: rec.title,
              handle: rec.handle,
              price: `${rec.price.currency_code} ${rec.price.amount}`,
              image: rec.image?.url,
              inStock: rec.available ?? true,
              url: rec.url,
            }),
          );

          setProducts(transformedProducts);

          // Create recommendation session with viewed products
          const viewedProducts: ViewedProduct[] = transformedProducts.map(
            (product, index) => ({
              product_id: product.id,
              position: index + 1,
            }),
          );

          await analyticsApi.createSession({
            extension_type: "venus",
            context,
            user_id: customerId,
            session_id: sessionId,
            viewed_products: viewedProducts,
            metadata: { source: `${context}_page` },
          });
        } else {
          throw new Error(`Failed to fetch ${context} recommendations`);
        }
      } catch (err) {
        console.error(`Error fetching ${context} recommendations:`, err);
        setError(`Failed to load recommendations`);
      } finally {
        setLoading(false);
      }
    };

    fetchRecommendations();
  }, [customerId, context, limit, sessionId, shopDomain]);

  return {
    loading,
    products,
    error,
    trackRecommendationClick,
    columnConfig: memoizedColumnConfig,
  };
}
