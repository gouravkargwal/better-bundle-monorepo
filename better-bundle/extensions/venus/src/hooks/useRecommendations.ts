import { useState, useEffect, useMemo } from "react";
import {
  recommendationApi,
  type ProductRecommendation,
  type ExtensionContext,
} from "../api/recommendations";
import { analyticsApi } from "../api/analytics";
import { useApi } from "@shopify/ui-extensions-react/customer-account";
import { logger } from "../utils/logger";

// Format price using the same logic as the Remix app
const formatPrice = (amount: string, currencyCode: string): string => {
  try {
    const numericAmount = parseFloat(amount);

    // Use Intl.NumberFormat for proper currency formatting (same as Remix app)
    const formatter = new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currencyCode,
      minimumFractionDigits:
        currencyCode === "JPY" || currencyCode === "KRW" ? 0 : 2,
      maximumFractionDigits:
        currencyCode === "JPY" || currencyCode === "KRW" ? 0 : 2,
    });

    return formatter.format(numericAmount);
  } catch (error) {
    // Fallback to simple symbol + amount
    const currencySymbols: { [key: string]: string } = {
      USD: "$",
      EUR: "€",
      GBP: "£",
      CAD: "C$",
      AUD: "A$",
      JPY: "¥",
      INR: "₹",
      KRW: "₩",
      BRL: "R$",
      MXN: "$",
    };
    const symbol = currencySymbols[currencyCode] || currencyCode;
    return `${symbol}${amount}`;
  }
};

interface Product {
  id: string;
  title: string;
  handle: string;
  price: string;
  image: {
    url: string;
    alt_text?: string;
  } | null;
  images?: Array<{
    url: string;
    alt_text?: string;
    type?: string;
    position?: number;
  }>;
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
          setSessionId(cachedSessionId);
          return;
        }

        // 2. If not in storage, fetch from backend API
        const sessionId = await analyticsApi.getOrCreateSession(
          shopDomain,
          customerId,
        );
        await storage.write("unified_session_id", sessionId);
        setSessionId(sessionId);
      } catch (err) {
        logger.error(
          {
            error: err instanceof Error ? err.message : String(err),
            shop_domain: shopDomain,
          },
          "Failed to initialize session",
        );
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
    try {
      const result = await analyticsApi.trackRecommendationClick(
        shopDomain,
        context,
        productId,
        position,
        sessionId,
        customerId,
        { source: `${context}_recommendation` },
      );

      // Handle session recovery if the API returned a new session
      if (result.success && result.sessionRecovery) {
        await storage.write(
          "unified_session_id",
          result.sessionRecovery.new_session_id,
        );
        setSessionId(result.sessionRecovery.new_session_id);
      }
    } catch (error) {
      logger.error(
        {
          error: error instanceof Error ? error.message : String(error),
          shop_domain: shopDomain,
        },
        "Failed to track recommendation click",
      );
    }

    return productUrl;
  };

  // Track recommendation view when user actually views them
  const trackRecommendationView = async () => {
    if (products.length === 0) {
      return;
    }

    try {
      const productIds = products.map((product) => product.id);
      const result = await analyticsApi.trackRecommendationView(
        shopDomain,
        context,
        sessionId,
        customerId,
        productIds,
        { source: `${context}_page` },
      );

      // Handle session recovery if the API returned a new session
      if (result.success && result.sessionRecovery) {
        await storage.write(
          "unified_session_id",
          result.sessionRecovery.new_session_id,
        );
        setSessionId(result.sessionRecovery.new_session_id);
      }
    } catch (error) {
      logger.error(
        {
          error: error instanceof Error ? error.message : String(error),
          shop_domain: shopDomain,
        },
        "Failed to track recommendation view",
      );
    }
  };

  // Fetch recommendations
  useEffect(() => {
    if (!sessionId) {
      logger.error(
        {
          shop_domain: shopDomain,
        },
        "Waiting for session initialization",
      );
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
              price: formatPrice(rec.price.amount, rec.price.currency_code),
              image: rec.image,
              images: rec.images || [],
              inStock: rec.available ?? true,
              url:
                rec.url ||
                (shopDomain
                  ? `https://${shopDomain}/products/${rec.handle}`
                  : rec.handle),
              variants: rec.variants || [],
            }),
          );

          setProducts(transformedProducts);
        } else {
          throw new Error(`Failed to fetch ${context} recommendations`);
        }
      } catch (err) {
        logger.error(
          {
            error: err instanceof Error ? err.message : String(err),
            shop_domain: shopDomain,
          },
          "Failed to fetch recommendations",
        );
        setError("Failed to load recommendations");
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
