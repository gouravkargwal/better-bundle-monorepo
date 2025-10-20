import { useState, useEffect, useMemo, useRef } from "preact/hooks";
import {
  recommendationApi,
} from "../api/recommendations";
import { analyticsApi } from "../api/analytics";

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

  useEffect(() => {
    const initializeSession = async () => {
      try {
        // 1. Try reading from storage first (fastest) - with expiration check
        const cachedSessionId = await storage.read("unified_session_id");
        const cachedExpiry = await storage.read("unified_session_expires_at");

        if (cachedSessionId && cachedExpiry && Date.now() < parseInt(cachedExpiry)) {
          console.log(
            "🔗 Mercury: Using cached session_id from storage:",
            cachedSessionId,
          );
          setSessionId(cachedSessionId);
          return;
        }

        if (cachedSessionId && cachedExpiry) {
          console.log("⚠️ Mercury: Cached session expired, creating new session");
        }

        // 2. If not in storage, fetch from backend API
        console.log("🌐 Mercury: Fetching session_id from backend");
        const sessionId = await analyticsApi.getOrCreateSession(
          shopDomain,
          customerId,
        );

        // Store session with expiration (30 minutes like Atlas)
        const expiresAt = Date.now() + 30 * 60 * 1000; // 30 minutes from now
        await storage.write("unified_session_id", sessionId);
        await storage.write("unified_session_expires_at", expiresAt.toString());

        console.log("✨ Mercury: Session initialized from backend:", sessionId);
        setSessionId(sessionId);
      } catch (err) {
        console.error("❌ Mercury: Failed to initialize session:", err);
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

  const trackRecommendationClick = async (
    productId,
    position,
    productUrl,
  ) => {
    try {
      const success = await analyticsApi.trackRecommendationClick(
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
        console.warn("⚠️ Mercury: Click tracking failed, clearing cached session");
        await storage.remove("unified_session_id");
        setSessionId(null);
      }
    } catch (error) {
      console.error(`Failed to track ${context} click:`, error);
      // Clear cached session on error
      await storage.remove("unified_session_id");
      setSessionId(null);
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
      const success = await analyticsApi.trackRecommendationView(
        shopDomain,
        context,
        sessionId,
        customerId,
        productIds,
        { source: `${context}_page` },
      );

      if (success) {
        console.log(`✅ Mercury: Recommendation view tracked for ${context}`);
      } else {
        // If tracking failed, clear cached session and retry
        console.warn("⚠️ Mercury: Tracking failed, clearing cached session");
        await storage.remove("unified_session_id");
        setSessionId(null);
        // The useEffect will automatically create a new session
      }
    } catch (error) {
      console.error(`❌ Mercury: Failed to track recommendation view:`, error);
      // Clear cached session on error
      await storage.remove("unified_session_id");
      setSessionId(null);
    }
  };

  // Fetch recommendations
  useEffect(() => {
    if (!sessionId) {
      console.log("⏳ Mercury: Waiting for session initialization");
      return;
    }

    if (hasFetchedRecommendations.current) {
      console.log("⏳ Mercury: Recommendations already fetched");
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
        console.error(`Error fetching ${context} recommendations:`, err);
        setError(`Failed to load recommendations`);
      } finally {
        setLoading(false);
      }
    };

    fetchRecommendations();
  }, [customerId, context, limit, sessionId, shopDomain, memoizedCartData]);

  return {
    loading,
    products,
    error,
    trackRecommendationClick,
    trackRecommendationView,
  };
}