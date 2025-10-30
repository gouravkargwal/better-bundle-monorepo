import { useState, useEffect } from "react";
import {
  recommendationApi,
  type ProductRecommendation,
  type ExtensionContext,
} from "../api/recommendations";
import { analyticsApi } from "../api/analytics";
import { logger } from "../utils/logger";
import { useJWT } from "./useJWT";

// Check if we're in design mode
const isDesignMode = (): boolean => {
  return (
    (window as Window & { Shopify?: { designMode?: boolean } }).Shopify
      ?.designMode || false
  );
};

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
  variants?: any[];
  options?: any[];
}

// Generate dummy products for design mode
const generateDummyProducts = (
  count: number,
  currency: string = "USD",
): Product[] => {
  return Array.from({ length: count }, (_, i) => {
    const basePrice = 29.99 + i * 10;
    const imageUrl = `https://via.placeholder.com/300x300/4a90e2/ffffff?text=Product+${i + 1}`;

    return {
      id: `dummy-${i}`,
      title: `Sample Product ${i + 1}`,
      handle: `sample-product-${i + 1}`,
      price: formatPrice(String(basePrice), currency),
      image: {
        url: imageUrl,
        alt_text: `Sample Product ${i + 1}`,
      },
      images: [
        {
          url: imageUrl,
          alt_text: `Sample Product ${i + 1}`,
          position: 0,
        },
        {
          url: `https://via.placeholder.com/300x300/ff6b6b/ffffff?text=Alt+${i + 1}`,
          alt_text: `Alternative view ${i + 1}`,
          position: 1,
        },
      ],
      inStock: true,
      url: "#",
      variant_id: `var-${i}-1`,
    };
  });
};

interface UseRecommendationsProps {
  context: ExtensionContext;
  limit: number;
  customerId: string;
  shopDomain?: string;
  currency?: string;
}

export function useRecommendations({
  context,
  limit,
  customerId,
  shopDomain,
  currency = "USD",
}: UseRecommendationsProps) {
  const { makeAuthenticatedRequest, isReady } = useJWT(shopDomain, customerId);
  const [loading, setLoading] = useState(false);
  const [products, setProducts] = useState<Product[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [designMode, setDesignMode] = useState(false);

  // Check for design mode on mount
  useEffect(() => {
    const inDesignMode = isDesignMode();
    setDesignMode(inDesignMode);

    if (inDesignMode) {
      // Return dummy products immediately in design mode
      setProducts(generateDummyProducts(limit, currency));
      setLoading(false);
      return;
    }
  }, [limit, currency]);

  // Set up JWT authentication for APIs
  useEffect(() => {
    if (isReady && makeAuthenticatedRequest) {
      recommendationApi.setJWT(makeAuthenticatedRequest);
      analyticsApi.setJWT(makeAuthenticatedRequest);
    }
  }, [isReady, makeAuthenticatedRequest]);

  useEffect(() => {
    // Skip session initialization in design mode
    if (designMode) {
      return;
    }

    const initializeSession = async () => {
      try {
        // 1. Try reading from storage first (fastest)
        const cachedSessionId = sessionStorage.getItem("unified_session_id");
        if (cachedSessionId) {
          setSessionId(cachedSessionId);
          return;
        }

        // 2. If not in storage, fetch from backend API
        const sessionId = await analyticsApi.getOrCreateSession(
          shopDomain,
          customerId,
        );
        sessionStorage.setItem("unified_session_id", sessionId);
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

    // Only initialize session if JWT is ready
    if (isReady) {
      initializeSession();
    }
  }, [shopDomain, customerId, isReady, designMode]);

  const trackRecommendationClick = async (
    productId: string,
    position: number,
    productUrl: string,
  ): Promise<string> => {
    // Skip tracking in design mode
    if (designMode) {
      return productUrl;
    }

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
        sessionStorage.setItem(
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
    // Skip tracking in design mode
    if (designMode || !products || products.length === 0) {
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
        sessionStorage.setItem(
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
    // Skip fetching in design mode
    if (designMode) {
      return;
    }

    if (!sessionId || !isReady) {
      logger.error(
        {
          shop_domain: shopDomain,
        },
        "Waiting for session and JWT initialization",
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
              options: (rec as any).options || [],
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
  }, [customerId, context, limit, sessionId, shopDomain, isReady, designMode]);

  return {
    loading,
    products,
    error,
    isDesignMode: designMode,
    trackRecommendationClick,
    trackRecommendationView,
  };
}
