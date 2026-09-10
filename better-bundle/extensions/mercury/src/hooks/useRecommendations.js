import { useState, useEffect, useMemo, useRef } from "preact/hooks";
import { getRecommendations } from "../api/recommendations";
import { recordOfferOutcome } from "../api/analytics";
import { logger } from "../utils/logger";

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
  // When true, no request is made and no impression is recorded. Set by the
  // caller when the extension is rendering in the checkout editor: a merchant
  // positioning the block is not a shopper being shown an offer, and counting
  // them inflates "offers shown" with traffic that could never convert.
  skip = false,
  context,
  limit,
  customerId,
  // Stable measurement id for this shopper, read from the `_bb_session` cart
  // attribute. Without it the backend cannot bucket the shopper into the
  // holdout — so the offer is served but excluded from the lift calculation —
  // and the impression it writes has no identity to join a later order on.
  sessionId,
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
  const hasFetchedRecommendations = useRef(false);
  const previousCartItemsRef = useRef([]); // Track previous cart items to detect real changes

  // No session bootstrap: `/api/session/get-or-create-session` was removed
  // with the behaviour-tracking pipeline. Recommendations are keyed on the cart
  // contents, and holdout bucketing uses the customer id, which checkout has.

  // Memoize cart data to prevent infinite re-renders
  const memoizedCartData = useMemo(() => ({
    cartItems: cartItems || [],
    cartValue: cartValue || 0,
    checkoutStep: checkoutStep || "order_summary",
  }), [cartItems, cartValue, checkoutStep]);

  // Report a click-through, then hand back the URL to navigate to.
  //
  // Used where the shopper leaves for the product's own page rather than
  // adding in place — the Thank You surface, where the order is already
  // complete and no cart write is possible.
  const trackRecommendationClickHandler = async (
    productId,
    position,
    productUrl,
    impressionId,
  ) => {
    if (impressionId) {
      await recordOfferOutcome(impressionId, "clicked");
    }
    return productUrl;
  };

  // No view reporting: the impression row is written server-side the moment
  // recommendations are served, so the client has nothing to add.

  // Fetch recommendations
  // ✅ Only refetch if cart items actually changed (new items added), not just cart value
  useEffect(() => {
    if (skip || !storage) {
      return;
    }

    // Check if cart items actually changed (new items added)
    const currentCartItems = JSON.stringify(memoizedCartData.cartItems.sort());
    const previousCartItems = JSON.stringify(previousCartItemsRef.current.sort());
    const cartItemsChanged = currentCartItems !== previousCartItems;

    // Only refetch if:
    // 1. First load (hasFetchedRecommendations is false), OR
    // 2. Cart items actually changed (new product added/removed)
    // Don't refetch just because cart value changed
    if (hasFetchedRecommendations.current && !cartItemsChanged) {
      return;
    }

    // Update previous cart items for next comparison
    previousCartItemsRef.current = [...(memoizedCartData.cartItems || [])];

    const fetchRecommendations = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await getRecommendations(storage, {
          context,
          limit,
          user_id: customerId,
          ...(sessionId && { session_id: sessionId }),
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
              price_amount: parseFloat(rec.price.amount), // numeric price for outcome tracking
              image: rec.image,
              images: rec.images,
              inStock: rec.available ?? true,
              url: rec.url,
              impression_id: rec.impression_id, // for incrementality outcome callback
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

    // ✅ Fetch recommendations (only if cart items changed or first load)
    fetchRecommendations();
  }, [
    skip,
    customerId,
    sessionId,
    context,
    limit,
    shopDomain,
    memoizedCartData,
    storage,
  ]);

  return {
    loading,
    products,
    error,
    trackRecommendationClick: trackRecommendationClickHandler,
  };
}
