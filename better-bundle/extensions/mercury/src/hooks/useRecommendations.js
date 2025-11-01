import { useState, useEffect, useMemo, useRef } from "preact/hooks";
import { getRecommendations } from "../api/recommendations";
import {
  getOrCreateSession,
  trackRecommendationView,
  trackRecommendationClick,
} from "../api/analytics";
import { logger } from "../utils/logger";
import { STORAGE_KEYS } from "../config/constants";

// Format price using the same logic as the Remix app
const formatPrice = (amount, currencyCode) => {
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
    const currencySymbols = {
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

export function useRecommendations({
  context,
  limit,
  customerId,
  shopDomain,
  storage,
  // Cart data for better recommendations
  cartItems,
  cartValue,
  checkoutStep,
}) {
  const [loading, setLoading] = useState(false);
  const [products, setProducts] = useState([]);
  const [error, setError] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const hasFetchedRecommendations = useRef(false);

  // Initialize session
  useEffect(() => {
    if (!storage || !shopDomain) {
      return;
    }

    const initializeSession = async () => {
      try {
        // 1. Try reading from storage first (fastest) - with expiration check
        const cachedSessionId = await storage.read(STORAGE_KEYS.SESSION_ID);
        const cachedExpiry = await storage.read(STORAGE_KEYS.SESSION_EXPIRES_AT);

        if (cachedSessionId && cachedExpiry && Date.now() < parseInt(cachedExpiry)) {
          setSessionId(cachedSessionId);
          return;
        }

        // 2. If not in storage, fetch from backend API
        const sessionId = await getOrCreateSession(
          storage,
          shopDomain,
          customerId,
        );

        // Store session with expiration (30 minutes like Atlas)
        const expiresAt = Date.now() + 30 * 60 * 1000; // 30 minutes from now
        await storage.write(STORAGE_KEYS.SESSION_ID, sessionId);
        await storage.write(STORAGE_KEYS.SESSION_EXPIRES_AT, expiresAt.toString());

        setSessionId(sessionId);
      } catch (err) {
        logger.error("Failed to initialize session:", err);
        setError("Failed to initialize session");
      }
    };

    initializeSession();
  }, [storage, shopDomain, customerId]);

  // Memoize cart data to prevent infinite re-renders
  const memoizedCartData = useMemo(() => ({
    cartItems: cartItems || [],
    cartValue: cartValue || 0,
    checkoutStep: checkoutStep || "order_summary",
  }), [cartItems, cartValue, checkoutStep]);

  const trackRecommendationClickHandler = async (
    productId,
    position,
    productUrl,
  ) => {
    try {
      if (!sessionId || !storage) {
        return productUrl;
      }

      const success = await trackRecommendationClick(
        storage,
        shopDomain,
        context,
        productId,
        position,
        sessionId,
        customerId,
        { source: `${context}_recommendation` },
      );

      if (!success) {
        // If tracking failed, clear cached session
        await storage.remove(STORAGE_KEYS.SESSION_ID);
        setSessionId(null);
      }
    } catch (error) {
      logger.error(`Failed to track ${context} click:`, error);
      // Clear cached session on error
      await storage.remove(STORAGE_KEYS.SESSION_ID);
      setSessionId(null);
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
      const success = await trackRecommendationView(
        storage,
        shopDomain,
        context,
        sessionId,
        customerId,
        productIds,
        { source: `${context}_page` },
      );

      if (!success) {
        await storage.remove(STORAGE_KEYS.SESSION_ID);
        setSessionId(null);
      }
    } catch (error) {
      logger.error(`Failed to track recommendation view:`, error);
      // Clear cached session on error
      await storage.remove(STORAGE_KEYS.SESSION_ID);
      setSessionId(null);
    }
  };

  // Fetch recommendations
  useEffect(() => {
    if (!storage || !sessionId) {
      return;
    }

    if (hasFetchedRecommendations.current) {
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
          ...(shopDomain && { shop_domain: shopDomain }),
          // Pass cart data for better recommendations
          cart_items: memoizedCartData.cartItems,
          cart_value: memoizedCartData.cartValue,
          checkout_step: memoizedCartData.checkoutStep,
          metadata: {
            mercury_checkout: true,
            checkout_type: "one_page",
            checkout_step: memoizedCartData.checkoutStep,
            cart_value: memoizedCartData.cartValue,
            cart_items: memoizedCartData.cartItems,
            block: "checkout.order-summary.render",
          },
        });

        if (response.success && response.recommendations) {
          // Transform API response to component format
          const transformedProducts = response.recommendations.map(
            (rec) => ({
              id: rec.id,
              title: rec.title,
              handle: rec.handle,
              price: formatPrice(rec.price.amount, rec.price.currency_code),
              image: rec.image,
              images: rec.images,
              inStock: rec.available ?? true,
              url: rec.url,
              // Transform variants to have 'id' instead of 'variant_id'
              variants: (rec.variants || []).map(variant => ({
                id: variant.variant_id,
                title: variant.title,
                price: variant.price,
                compare_at_price: variant.compare_at_price,
                sku: variant.sku,
                barcode: variant.barcode,
                inventory: variant.inventory,
                currency_code: variant.currency_code
              })),
              // Also include the selected variant ID for easy access
              selectedVariantId: rec.selectedVariantId || rec.variant_id,
              // Include options for dropdowns
              options: rec.options || [],
            }),
          );

          setProducts(transformedProducts);
          hasFetchedRecommendations.current = true;
        } else {
          throw new Error(`Failed to fetch ${context} recommendations`);
        }
      } catch (err) {
        logger.error(`Error fetching ${context} recommendations:`, err);
        setError(`Failed to load recommendations`);
      } finally {
        setLoading(false);
      }
    };

    fetchRecommendations();
  }, [customerId, context, limit, sessionId, shopDomain, memoizedCartData, storage]);

  return {
    loading,
    products,
    error,
    trackRecommendationClick: trackRecommendationClickHandler,
    trackRecommendationView: trackRecommendationViewHandler,
  };
}
