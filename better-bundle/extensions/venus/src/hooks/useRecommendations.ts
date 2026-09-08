import { useState, useEffect, useMemo } from "react";
import {
  getRecommendations,
  type ProductRecommendation,
  type ExtensionContext,
} from "../api/recommendations";
import {
  getOrCreateSession,
  trackRecommendationView as trackRecommendationViewAPI,
  trackRecommendationClick as trackRecommendationClickAPI,
} from "../api/analytics";
import { useApi } from "@shopify/ui-extensions-react/customer-account";
import { logger } from "../utils/logger";
import { STORAGE_KEYS } from "../config/constants";

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

  // Initialize session
  useEffect(() => {
    if (!storage || !shopDomain) {
      return;
    }

    const initializeSession = async () => {
      try {
        // 1. Try reading from storage first (fastest) - with expiration check
        const cachedSessionId = await storage.read(STORAGE_KEYS.SESSION_ID);
        const cachedExpiry = await storage.read(
          STORAGE_KEYS.SESSION_EXPIRES_AT,
        );

        if (
          cachedSessionId &&
          cachedExpiry &&
          Date.now() < parseInt(cachedExpiry as string)
        ) {
          setSessionId(cachedSessionId as string);
          return;
        }

        // 2. If not in storage, fetch from backend API
        const sessionId = await getOrCreateSession(
          storage,
          shopDomain,
          customerId,
        );

        // Store session with expiration (30 minutes like Atlas/Mercury)
        const expiresAt = Date.now() + 30 * 60 * 1000; // 30 minutes from now
        await storage.write(STORAGE_KEYS.SESSION_ID, sessionId);
        await storage.write(
          STORAGE_KEYS.SESSION_EXPIRES_AT,
          expiresAt.toString(),
        );

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
      if (!sessionId || !storage) {
        return productUrl;
      }

      const success = await trackRecommendationClickAPI(
        storage,
        shopDomain,
        context,
        productId,
        position,
        sessionId,
        customerId,
        { source: `${context}_recommendation` },
      );

      // Note: We don't delete session on tracking failure
      // - Network errors don't invalidate the session
      // - Session recovery is handled by trackUnifiedInteraction
      // - Session will expire naturally after 30 minutes
      if (!success) {
        // Just log - session may still be valid for next request
        logger.warn(
          "Recommendation click tracking failed, but keeping session",
        );
      }
    } catch (error) {
      logger.error(
        {
          error: error instanceof Error ? error.message : String(error),
          shop_domain: shopDomain,
        },
        "Failed to track recommendation click",
      );
      // Don't delete session on error - might be network issue
      // Session recovery will happen automatically if needed
    }

    return productUrl;
  };

  // Track recommendation view when user actually views them
  const trackRecommendationViewHandler = async () => {
    if (products.length === 0 || !sessionId || !storage) {
      return;
    }

    try {
      const productIds = products.map((product) => product.id);
      const success = await trackRecommendationViewAPI(
        storage,
        shopDomain,
        context,
        sessionId,
        customerId,
        productIds,
        { source: `${context}_page` },
      );

      // Note: We don't delete session on tracking failure
      // - Network errors don't invalidate the session
      // - Session recovery is handled by trackUnifiedInteraction
      // - Session will expire naturally after 30 minutes
      if (!success) {
        // Just log - session may still be valid for next request
        logger.warn("Recommendation view tracking failed, but keeping session");
      }
    } catch (error) {
      logger.error(
        {
          error: error instanceof Error ? error.message : String(error),
          shop_domain: shopDomain,
        },
        "Failed to track recommendation view",
      );
      // Don't delete session on error - might be network issue
      // Session recovery will happen automatically if needed
    }
  };

  // Fetch recommendations
  useEffect(() => {
    if (!storage || !sessionId) {
      return;
    }

    const fetchRecommendations = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await getRecommendations(storage, {
          context,
          limit,
          user_id: customerId,
          session_id: sessionId,
          shop_domain: shopDomain,
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
  }, [customerId, context, limit, sessionId, shopDomain, storage]);

  return {
    loading,
    products,
    error,
    trackRecommendationClick,
    trackRecommendationView: trackRecommendationViewHandler,
    columnConfig: memoizedColumnConfig,
  };
}
