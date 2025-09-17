import type { AtlasConfig } from "../types";

// Unified Analytics API endpoints
const UNIFIED_ANALYTICS_BASE_URL = "https://d242bda5e5c7.ngrok-free.app";

// Session management
let currentSessionId: string | null = null;
let sessionExpiresAt: number | null = null;

/**
 * Get or create a session for Atlas tracking
 */
export const getOrCreateSession = async (
  config: AtlasConfig,
  customerId?: string,
): Promise<string> => {
  // Check if we have a valid session
  if (currentSessionId && sessionExpiresAt && Date.now() < sessionExpiresAt) {
    return currentSessionId;
  }

  try {
    const url = `${UNIFIED_ANALYTICS_BASE_URL}/api/atlas/get-or-create-session`;

    const payload = {
      shop_id: config.shopDomain?.replace(".myshopify.com", "") || "",
      customer_id: customerId || null,
      browser_session_id: getBrowserSessionId(),
      user_agent: navigator.userAgent,
      ip_address: null, // Will be detected server-side
      referrer: document.referrer,
      page_url: window.location.href,
    };

    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      keepalive: true,
    });

    if (!response.ok) {
      throw new Error(`Session creation failed: ${response.status}`);
    }

    const result = await response.json();

    if (result.success && result.data && result.data.session_id) {
      const sessionId = result.data.session_id;
      currentSessionId = sessionId;
      // Set session to expire 30 minutes from now (server handles actual expiration)
      sessionExpiresAt = Date.now() + 30 * 60 * 1000;

      console.log("🔄 Atlas session created/retrieved:", sessionId);
      return sessionId;
    } else {
      throw new Error(result.message || "Failed to create session");
    }
  } catch (error) {
    console.error("💥 Session creation error:", error);
    throw error;
  }
};

/**
 * Track interaction using unified analytics
 */
export const trackInteraction = async (
  event: any,
  config: AtlasConfig,
  customerId?: string,
): Promise<void> => {
  try {
    // Get or create session first
    const sessionId = await getOrCreateSession(config, customerId);

    // Map Shopify event to unified analytics format
    const interactionData = mapShopifyEventToUnified(
      event,
      sessionId,
      config,
      customerId,
    );

    // Send to unified analytics endpoint
    const url = `${UNIFIED_ANALYTICS_BASE_URL}/api/atlas/track-interaction`;

    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(interactionData),
      keepalive: true,
    });

    if (!response.ok) {
      throw new Error(`Interaction tracking failed: ${response.status}`);
    }

    const result = await response.json();

    if (result.success) {
      console.log("✅ Atlas interaction tracked:", result.data?.interaction_id);
    } else {
      throw new Error(result.message || "Failed to track interaction");
    }
  } catch (error) {
    console.error("💥 Interaction tracking error:", error);
    // Don't throw - we don't want to break the user experience
  }
};

/**
 * Map Shopify event to unified analytics format
 */
const mapShopifyEventToUnified = (
  event: any,
  sessionId: string,
  config: AtlasConfig,
  customerId?: string,
) => {
  const baseData = {
    session_id: sessionId,
    shop_id: config.shopDomain?.replace(".myshopify.com", "") || "",
    customer_id: customerId || null,
    metadata: {
      ...event,
      source: "atlas_web_pixel",
      page_url: window.location.href,
      referrer: document.referrer,
      timestamp: new Date().toISOString(),
    },
  };

  // Map based on event type
  switch (event.name) {
    case "page_viewed":
      return {
        ...baseData,
        context: detectPageContext(window.location.href),
        interaction_type: "page_view",
        time_on_page: event.timeOnPage || null,
        scroll_depth: event.scrollDepth || null,
      };

    case "product_viewed":
      return {
        ...baseData,
        context: "product_page",
        interaction_type: "product_view",
        product_id:
          event.data?.productVariant?.product?.id || event.data?.product?.id,
        metadata: {
          ...baseData.metadata,
          product_title:
            event.data?.productVariant?.product?.title ||
            event.data?.product?.title,
          product_price:
            event.data?.productVariant?.price?.amount ||
            event.data?.product?.price?.amount,
          product_variant_id: event.data?.productVariant?.id,
        },
      };

    case "product_added_to_cart":
      return {
        ...baseData,
        context: detectPageContext(window.location.href),
        interaction_type: "add_to_cart",
        product_id:
          event.data?.productVariant?.product?.id || event.data?.product?.id,
        metadata: {
          ...baseData.metadata,
          product_title:
            event.data?.productVariant?.product?.title ||
            event.data?.product?.title,
          product_price:
            event.data?.productVariant?.price?.amount ||
            event.data?.product?.price?.amount,
          quantity: event.data?.quantity || 1,
        },
      };

    case "product_removed_from_cart":
      return {
        ...baseData,
        context: "cart_page",
        interaction_type: "remove_from_cart",
        product_id:
          event.data?.productVariant?.product?.id || event.data?.product?.id,
        metadata: {
          ...baseData.metadata,
          product_title:
            event.data?.productVariant?.product?.title ||
            event.data?.product?.title,
          quantity: event.data?.quantity || 1,
        },
      };

    case "cart_viewed":
      return {
        ...baseData,
        context: "cart_page",
        interaction_type: "page_view",
        metadata: {
          ...baseData.metadata,
          cart_value: event.data?.cart?.cost?.totalAmount?.amount,
          cart_items_count: event.data?.cart?.lines?.length || 0,
        },
      };

    case "collection_viewed":
      return {
        ...baseData,
        context: "collection_page",
        interaction_type: "page_view",
        collection_id: event.data?.collection?.id,
        metadata: {
          ...baseData.metadata,
          collection_title: event.data?.collection?.title,
          collection_handle: event.data?.collection?.handle,
        },
      };

    case "search_submitted":
      return {
        ...baseData,
        context: "search_page",
        interaction_type: "search",
        search_query: event.data?.searchResult?.query,
        metadata: {
          ...baseData.metadata,
          search_results_count: event.data?.searchResult?.results?.length || 0,
        },
      };

    case "checkout_started":
      return {
        ...baseData,
        context: "checkout_page",
        interaction_type: "page_view",
        metadata: {
          ...baseData.metadata,
          checkout_value: event.data?.checkout?.totalPrice?.amount,
          checkout_items_count: event.data?.checkout?.lineItems?.length || 0,
        },
      };

    case "checkout_completed":
      return {
        ...baseData,
        context: "checkout_page",
        interaction_type: "purchase",
        metadata: {
          ...baseData.metadata,
          order_id: event.data?.checkout?.order?.id,
          order_value: event.data?.checkout?.totalPrice?.amount,
          order_items_count: event.data?.checkout?.lineItems?.length || 0,
        },
      };

    case "customer_linked":
      return {
        ...baseData,
        context: detectPageContext(window.location.href),
        interaction_type: "customer_linked",
        metadata: {
          ...baseData.metadata,
          client_id: event.clientId,
          linked_at: event.data?.linkedAt,
        },
      };

    default:
      // Generic interaction for unknown events
      return {
        ...baseData,
        context: detectPageContext(window.location.href),
        interaction_type: "other",
        metadata: {
          ...baseData.metadata,
          event_name: event.name,
          event_data: event.data,
        },
      };
  }
};

/**
 * Detect page context from URL
 */
const detectPageContext = (url: string): string => {
  if (url.includes("/products/")) return "product_page";
  if (url.includes("/collections/")) return "collection_page";
  if (url.includes("/cart")) return "cart_page";
  if (url.includes("/search")) return "search_page";
  if (url.includes("/account")) return "customer_account";
  if (url.includes("/checkout")) return "checkout_page";
  if (url.includes("/orders/")) return "order_page";
  return "homepage";
};

/**
 * Get browser session ID (fallback if no session exists)
 */
const getBrowserSessionId = (): string => {
  let sessionId = sessionStorage.getItem("atlas_session_id");
  if (!sessionId) {
    sessionId =
      "atlas_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
    sessionStorage.setItem("atlas_session_id", sessionId);
  }
  return sessionId;
};
