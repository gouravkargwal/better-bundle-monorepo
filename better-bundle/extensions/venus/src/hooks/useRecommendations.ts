import { useState, useEffect, useMemo } from "react";
import {
  recommendationApi,
  type ProductRecommendation,
  type ExtensionContext,
} from "../api/recommendations";
import { analyticsApi } from "../api/analytics";
import { useApi } from "@shopify/ui-extensions-react/customer-account";

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
  const { storage } = useApi();
  const [loading, setLoading] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    const initializeSession = async () => {
      try {
        // 1. Try reading from storage first (fastest)
        const cachedSessionId =
          await storage.read<string>("unified_session_id");

        if (cachedSessionId) {
          console.log(
            "🔗 Venus: Using cached session_id from storage:",
            cachedSessionId,
          );
          setSessionId(cachedSessionId);
          return;
        }

        // 2. If not in storage, fetch from backend API
        console.log("🌐 Venus: Fetching session_id from backend");
        const sessionId = await analyticsApi.getOrCreateSession(
          shopDomain,
          customerId,
        );
        await storage.write("unified_session_id", sessionId);
        console.log("✨ Venus: Session initialized from backend:", sessionId);
        setSessionId(sessionId);
      } catch (err) {
        console.error("❌ Venus: Failed to initialize session:", err);
        setError("Failed to initialize session");
      }
    };

    initializeSession();
  }, [storage, shopDomain, customerId]);

  // Memoized column configuration
  const memoizedColumnConfig = useMemo(() => columnConfig, [columnConfig]);

  const trackRecommendationClick = async (
    productId: string,
    position: number,
    productUrl: string,
  ): Promise<string> => {
    analyticsApi
      .trackRecommendationClick(
        shopDomain,
        context,
        productId,
        position,
        sessionId,
        customerId,
        { source: `${context}_recommendation` },
      )
      .catch((error) => {
        console.error(`Failed to track ${context} click:`, error);
      });

    return productUrl;
  };

  // Track recommendation view when user actually views them
  const trackRecommendationView = async () => {
    if (products.length === 0) {
      return;
    }

    try {
      const productIds = products.map((product) => product.id);
      await analyticsApi.trackRecommendationView(
        shopDomain,
        context,
        sessionId,
        customerId,
        productIds,
        { source: `${context}_page` },
      );
      console.log(`✅ Venus: Recommendation view tracked for ${context}`);
    } catch (error) {
      console.error(`❌ Venus: Failed to track recommendation view:`, error);
    }
  };

  // Fetch recommendations
  useEffect(() => {
    if (!sessionId) {
      console.log("⏳ Venus: Waiting for session initialization");
      return;
    }
    const fetchRecommendations = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await recommendationApi.getRecommendations({
          context,
          limit,
          user_id: customerId,
          session_id: sessionId,
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
    trackRecommendationView,
    columnConfig: memoizedColumnConfig,
  };
}
