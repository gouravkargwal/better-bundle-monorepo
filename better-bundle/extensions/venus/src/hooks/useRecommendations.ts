import { useState, useEffect, useMemo } from "react";
import {
  recommendationApi,
  type ProductRecommendation,
  type ExtensionContext,
} from "../api/recommendations";
import { analyticsApi } from "../api/analytics";

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
  context: ExtensionContext;
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
  ): Promise<string> => {
    // Track interaction using unified analytics (non-blocking)
    analyticsApi
      .trackRecommendationClick(
        shopDomain?.replace(".myshopify.com", "") || "",
        context,
        productId,
        position,
        customerId,
        { source: `${context}_recommendation` },
      )
      .catch((error) => {
        console.error(`Failed to track ${context} click:`, error);
      });

    // Store attribution in cart for order processing
    analyticsApi
      .storeCartAttribution(sessionId, productId, context, position)
      .catch((error) => {
        console.error(`Failed to store cart attribution:`, error);
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

    // Return product page URL with attribution immediately
    const productUrlWithAttribution = `${productUrl}?${attributionParams.toString()}`;
    console.log(
      `${context} recommendation clicked:`,
      productUrlWithAttribution,
    );

    return productUrlWithAttribution;
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

          // Track recommendation view using unified analytics
          const productIds = transformedProducts.map((product) => product.id);
          await analyticsApi.trackRecommendationView(
            shopDomain?.replace(".myshopify.com", "") || "",
            context,
            customerId,
            productIds,
            { source: `${context}_page` },
          );
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
