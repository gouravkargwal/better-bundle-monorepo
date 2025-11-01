/**
 * Unified Analytics API Client for BetterBundle Venus Extension
 *
 * Functional implementation matching Mercury/Atlas pattern
 */

import { BACKEND_URL, STORAGE_KEYS } from "../config/constants";
import { logger } from "../utils/logger";
import { makeAuthenticatedRequest } from "../utils/jwt";

// Unified Analytics Types
export type ExtensionContext =
  | "homepage"
  | "product_page"
  | "collection_page"
  | "cart_page"
  | "search_page"
  | "customer_account"
  | "checkout_page"
  | "order_page"
  | "thank_you_page"
  | "profile"
  | "order_status"
  | "order_history";

export type InteractionType =
  | "page_viewed"
  | "product_viewed"
  | "product_added_to_cart"
  | "product_removed_from_cart"
  | "cart_viewed"
  | "collection_viewed"
  | "search_submitted"
  | "checkout_started"
  | "checkout_completed"
  | "customer_linked"
  | "recommendation_viewed"
  | "recommendation_clicked"
  | "recommendation_add_to_cart";

// Unified Analytics Request Types
export interface UnifiedInteractionRequest {
  session_id: string;
  shop_domain: string;
  context: ExtensionContext;
  interaction_type: InteractionType;
  customer_id?: string;
  product_id?: string;
  collection_id?: string;
  search_query?: string;
  page_url?: string;
  client_id?: string;
  referrer?: string;
  time_on_page?: number;
  scroll_depth?: number;
  metadata: Record<string, any>;
}

export interface UnifiedResponse {
  success: boolean;
  message: string;
  data?: {
    session_id?: string;
    interaction_id?: string;
    customer_id?: string;
    browser_session_id?: string;
    expires_at?: string;
    extensions_used?: string[];
    context?: ExtensionContext;
    client_id?: string;
    [key: string]: any;
  };
  // Session recovery information
  session_recovery?: {
    original_session_id: string;
    new_session_id: string;
    recovery_reason: string;
    recovered_at: string;
  };
}

const getBrowserSessionIdFromStorage = async (
  storage: Storage,
): Promise<string | null> => {
  try {
    return await storage.read(STORAGE_KEYS.BROWSER_SESSION_ID);
  } catch (error) {
    // Browser session ID might not be available
    return null;
  }
};

const storeBrowserSessionId = async (
  storage: Storage,
  browserSessionId: string,
): Promise<void> => {
  try {
    await storage.write(STORAGE_KEYS.BROWSER_SESSION_ID, browserSessionId);
  } catch (error) {
    logger.warn({ error }, "Venus: Failed to store browser_session_id");
  }
};

const getOrStoreClientId = async (
  storage: Storage,
  clientId: string | null,
): Promise<string | null> => {
  let storedClientId = await storage.read(STORAGE_KEYS.CLIENT_ID);

  if (clientId && clientId !== storedClientId) {
    await storage.write(STORAGE_KEYS.CLIENT_ID, clientId);
    return clientId;
  }

  return storedClientId || null;
};

let sessionCreationPromise: Promise<string> | null = null;

/**
 * Helper function for updating client ID in background
 */
const updateClientIdInBackground = async (
  sessionId: string,
  clientId: string,
  shopDomain: string,
  storage: Storage,
  customerId?: string | null,
): Promise<void> => {
  // Skip if no client_id provided (Venus typically doesn't have access to it)
  if (!clientId) {
    return;
  }

  try {
    const url = `${BACKEND_URL}/api/session/update-client-id`;

    await makeAuthenticatedRequest(storage, url, {
      method: "POST",
      shopDomain,
      customerId: customerId || undefined,
      body: JSON.stringify({
        session_id: sessionId,
        client_id: clientId,
        shop_domain: shopDomain,
      }),
      keepalive: true,
    });
  } catch (error) {
    logger.error({ error }, "Venus pixel: Background client_id update failed");
  }
};

/**
 * Get or create session
 */
export const getOrCreateSession = async (
  storage,
  shopDomain: string,
  customerId?: string | null,
  pageUrl: string | null = null,
  referrer: string | null = null,
  userAgent: string | null = null,
  clientId: string | null = null,
): Promise<string> => {
  try {
    if (!storage) {
      throw new Error("Storage is required");
    }

    // Venus extension typically doesn't have access to client_id
    // We'll only use stored client_id if it exists (might be set by backend)
    const storedClientId = await getOrStoreClientId(storage, clientId);

    const storedSessionId = await storage.read(STORAGE_KEYS.SESSION_ID);
    const storedExpiresAt = await storage.read(STORAGE_KEYS.SESSION_EXPIRES_AT);

    if (
      storedSessionId &&
      storedExpiresAt &&
      Date.now() < parseInt(storedExpiresAt)
    ) {
      // Only update client_id if we have a new one (rare in Venus context)
      if (clientId && clientId !== storedClientId) {
        updateClientIdInBackground(
          storedSessionId,
          clientId,
          shopDomain,
          storage,
          customerId,
        ).catch((err) => {
          logger.error(
            { err },
            "Venus pixel: Failed to update client_id in background",
          );
        });
      }

      return storedSessionId;
    }

    if (sessionCreationPromise) {
      return await sessionCreationPromise;
    }

    sessionCreationPromise = (async () => {
      try {
        // Get browser_session_id from storage if available (backend-generated)
        // If not available, backend will generate it
        const storedBrowserSessionId =
          await getBrowserSessionIdFromStorage(storage);

        const url = `${BACKEND_URL}/api/session/get-or-create-session`;

        const payload = {
          shop_domain: shopDomain,
          customer_id: customerId || undefined, // Can be null for guest checkouts
          browser_session_id: storedBrowserSessionId || undefined, // Backend will generate if not provided
          client_id: storedClientId || clientId || undefined, // Venus doesn't have access, use stored or undefined
          user_agent: true,
          ip_address: true,
          referrer: referrer || undefined,
          page_url: pageUrl || undefined,
          extension_type: "venus",
        };

        // ✅ Use makeAuthenticatedRequest for automatic token refresh
        // customerId can be null for guest checkouts - JWT will handle it
        const response = await makeAuthenticatedRequest(storage, url, {
          method: "POST",
          shopDomain,
          customerId: customerId || undefined, // Pass undefined instead of null
          body: JSON.stringify(payload),
          keepalive: true,
        });

        if (!response.ok) {
          if (response.status === 403) {
            logger.error({ response }, "Venus pixel: Services suspended");
            throw new Error("Services suspended");
          }
          logger.error({ response }, "Venus pixel: Session creation failed");
          throw new Error(`Session creation failed: ${response.status}`);
        }

        const result: UnifiedResponse = await response.json();

        if (result.success && result.data && result.data.session_id) {
          const sessionId = result.data.session_id;
          const expiresAt = Date.now() + 30 * 60 * 1000; // 30 minutes from now

          await storage.write(STORAGE_KEYS.SESSION_ID, sessionId);
          await storage.write(
            STORAGE_KEYS.SESSION_EXPIRES_AT,
            expiresAt.toString(),
          );

          if (result.data.client_id) {
            await storage.write(STORAGE_KEYS.CLIENT_ID, result.data.client_id);
          }

          // ✅ Store backend-generated browser_session_id
          if (result.data.browser_session_id) {
            await storeBrowserSessionId(
              storage,
              result.data.browser_session_id,
            );
          }

          return sessionId;
        } else {
          logger.error({ result }, "Venus pixel: Failed to create session");
          throw new Error(result.message || "Failed to create session");
        }
      } catch (error) {
        logger.error({ error }, "Venus pixel: Failed to create session");
        throw error;
      } finally {
        sessionCreationPromise = null;
      }
    })();
    return await sessionCreationPromise;
  } catch (error) {
    logger.error("Session creation error:", error);
    throw error;
  }
};

/**
 * Track interaction using unified analytics
 */
export const trackUnifiedInteraction = async (
  storage,
  request: UnifiedInteractionRequest,
): Promise<boolean> => {
  try {
    if (!storage) {
      throw new Error("Storage is required");
    }

    const interactionData = {
      session_id: request.session_id,
      shop_domain: request.shop_domain,
      extension_type: "venus", // ✅ Add this required field
      customer_id: request.customer_id || undefined, // Can be null for guest checkouts
      interaction_type: request.interaction_type,
      metadata: request.metadata || {},
    };

    // Send to unified analytics endpoint
    const url = `${BACKEND_URL}/api/interaction/track`;

    // ✅ Use makeAuthenticatedRequest for automatic token refresh
    // customerId can be null for guest checkouts
    const response = await makeAuthenticatedRequest(storage, url, {
      method: "POST",
      shopDomain: request.shop_domain,
      customerId: request.customer_id || undefined, // Pass undefined instead of null
      body: JSON.stringify(interactionData),
      keepalive: true,
    });

    if (!response.ok) {
      if (response.status === 403) {
        logger.error({ response }, "Venus pixel: Services suspended");
        throw new Error("Services suspended");
      }
      logger.error({ response }, "Venus pixel: Interaction tracking failed");
      throw new Error(`Interaction tracking failed: ${response.status}`);
    }

    const result: UnifiedResponse = await response.json();

    // Handle session recovery if it occurred
    if (result.session_recovery) {
      // Update stored session ID with the new one (unified with other extensions)
      await storage.write(
        STORAGE_KEYS.SESSION_ID,
        result.session_recovery.new_session_id,
      );
    }

    return true;
  } catch (error) {
    logger.error("Interaction tracking error:", error);
    return false;
  }
};

/**
 * Build recommendation metadata
 */
export const buildRecommendationMetadata = (params: {
  extensionType: "venus";
  source?: string;
  cartProductCount?: number;
  recommendationCount: number;
  recommendations: { id: string; position: number }[];
  widget?: string;
  algorithm?: string;
  // Any additional fields provided by caller should still be preserved
  extra?: Record<string, any>;
}): Record<string, any> => {
  const {
    extensionType,
    source = "venus_theme_extension",
    cartProductCount,
    recommendationCount,
    recommendations,
    widget = "venus_recommendation",
    algorithm = "venus_algorithm",
    extra = {},
  } = params;

  // Preserve any extra metadata keys but ensure required structure exists
  return {
    source,
    cart_product_count: cartProductCount ?? extra.cart_product_count ?? 0,
    recommendation_count: recommendationCount,
    extension_type: extensionType,
    data: {
      recommendations: recommendations.map((r) => ({
        id: String(r.id),
        position: r.position,
      })),
      type: "recommendation",
      widget: extra.widget ?? widget,
      algorithm: extra.algorithm ?? algorithm,
    },
    // Spread at the end so callers can add bespoke keys without breaking the schema
    ...extra,
  };
};

/**
 * Track recommendation view (when recommendations are displayed)
 */
export const trackRecommendationView = async (
  storage,
  shopDomain: string,
  context: ExtensionContext,
  sessionId: string,
  customerId?: string,
  productIds?: string[],
  metadata?: Record<string, any>,
): Promise<boolean> => {
  try {
    const recommendations = (productIds || []).map((id, index) => ({
      id,
      position: index + 1,
    }));

    const request: UnifiedInteractionRequest = {
      session_id: sessionId,
      shop_domain: shopDomain,
      context,
      interaction_type: "recommendation_viewed",
      customer_id: customerId,
      page_url: null,
      referrer: null,
      metadata: buildRecommendationMetadata({
        extensionType: "venus",
        recommendationCount: recommendations.length,
        recommendations,
        cartProductCount: metadata?.cart_product_count,
        extra: metadata,
      }),
    };

    return await trackUnifiedInteraction(storage, request);
  } catch (error) {
    logger.error("Failed to track recommendation view:", error);
    return false;
  }
};

/**
 * Track recommendation click (when user clicks on a recommendation)
 */
export const trackRecommendationClick = async (
  storage,
  shopDomain: string,
  context: ExtensionContext,
  productId: string,
  position: number,
  sessionId: string,
  customerId?: string,
  metadata?: Record<string, any>,
): Promise<boolean> => {
  try {
    const request: UnifiedInteractionRequest = {
      session_id: sessionId,
      shop_domain: shopDomain,
      context,
      interaction_type: "recommendation_clicked",
      customer_id: customerId,
      product_id: productId,
      page_url: null,
      referrer: null,
      metadata: {
        source: metadata?.source || "venus_recommendation",
        cart_product_count: metadata?.cart_product_count ?? 0,
        recommendation_count: 1,
        extension_type: "venus",
        data: {
          product: {
            id: productId,
          },
          position: position,
          type: "recommendation",
          widget: metadata?.widget || "venus_recommendation",
          algorithm: metadata?.algorithm || "venus_algorithm",
        },
        ...metadata,
      },
    };

    return await trackUnifiedInteraction(storage, request);
  } catch (error) {
    logger.error("Failed to track recommendation click:", error);
    return false;
  }
};
