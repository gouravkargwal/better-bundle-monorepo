import { BACKEND_URL, STORAGE_KEYS } from "../config/constants";
import { logger } from "../utils/logger";
import { makeAuthenticatedRequest } from "../utils/jwt";

const getBrowserSessionIdFromStorage = async (storage) => {
  try {
    return await storage.read(STORAGE_KEYS.BROWSER_SESSION_ID);
  } catch (error) {
    // localStorage not available in checkout extension context
    return null;
  }
};

const storeBrowserSessionId = async (storage, browserSessionId) => {
  try {
    await storage.write(STORAGE_KEYS.BROWSER_SESSION_ID, browserSessionId);
  } catch (error) {
    // localStorage not available in checkout extension context
    logger.warn({ error }, "Mercury: Failed to store browser_session_id");
  }
};

const getOrStoreClientId = async (storage, clientId) => {
  // Mercury extension doesn't have access to client_id from analytics
  // Only use stored client_id if it exists (might be set by backend)
  let storedClientId = await storage.read(STORAGE_KEYS.CLIENT_ID);

  // Only update if we have a new client_id AND it's different
  // (In Mercury context, clientId will typically be null)
  if (clientId && clientId !== storedClientId) {
    await storage.write(STORAGE_KEYS.CLIENT_ID, clientId);
    return clientId;
  }

  return storedClientId || null;
};

let sessionCreationPromise = null;

/**
 * Helper function for updating client ID in background
 * Note: Mercury extension typically doesn't have access to client_id,
 * so this is rarely called. Only used if backend provides a client_id.
 */
const updateClientIdInBackground = async (
  sessionId,
  clientId,
  shopDomain,
  storage,
  customerId,
) => {
  // Skip if no client_id provided (Mercury doesn't have access to it)
  if (!clientId) {
    return;
  }

  try {
    const url = `${BACKEND_URL}/api/session/update-client-id`;

    await makeAuthenticatedRequest(storage, url, {
      method: "POST",
      shopDomain,
      customerId,
      body: JSON.stringify({
        session_id: sessionId,
        client_id: clientId,
        shop_domain: shopDomain,
      }),
      keepalive: true,
    });
  } catch (error) {
    logger.error({ error }, "Mercury pixel: Background client_id update failed");
  }
};

/**
 * Get or create session
 */
export const getOrCreateSession = async (
  storage,
  shopDomain,
  customerId = null, // Can be null for guest checkouts
  pageUrl = null,
  referrer = null,
  userAgent = null,
  clientId = null, // Mercury doesn't have access to client_id, typically null
) => {
  try {
    if (!storage) {
      throw new Error("Storage is required");
    }

    // Mercury extension doesn't have access to client_id from analytics
    // We'll only use stored client_id if it exists (might be set by backend)
    const storedClientId = await getOrStoreClientId(storage, clientId);

    const storedSessionId = await storage.read(STORAGE_KEYS.SESSION_ID);
    const storedExpiresAt = await storage.read(STORAGE_KEYS.SESSION_EXPIRES_AT);

    if (
      storedSessionId &&
      storedExpiresAt &&
      Date.now() < parseInt(storedExpiresAt)
    ) {
      // Only update client_id if we have a new one (rare in Mercury context)
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
            "Mercury pixel: Failed to update client_id in background",
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
        const storedBrowserSessionId = await getBrowserSessionIdFromStorage(storage);

        const url = `${BACKEND_URL}/api/session/get-or-create-session`;

        const payload = {
          shop_domain: shopDomain,
          customer_id: customerId || undefined, // Can be null for guest checkouts
          browser_session_id: storedBrowserSessionId || undefined, // Backend will generate if not provided
          client_id: storedClientId || clientId || undefined, // Mercury doesn't have access, use stored or undefined
          user_agent: true,
          ip_address: true,
          referrer: referrer || undefined,
          page_url: pageUrl || undefined,
          extension_type: "mercury",
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
            logger.error({ response }, "Mercury pixel: Services suspended");
            throw new Error("Services suspended");
          }
          logger.error({ response }, "Mercury pixel: Session creation failed");
          throw new Error(`Session creation failed: ${response.status}`);
        }

        const result = await response.json();

        if (result.success && result.data && result.data.session_id) {
          const sessionId = result.data.session_id;
          const expiresAt = Date.now() + 30 * 60 * 1000; // 30 minutes from now

          await storage.write(STORAGE_KEYS.SESSION_ID, sessionId);
          await storage.write(
            STORAGE_KEYS.SESSION_EXPIRES_AT,
            expiresAt.toString(),
          );

          if (result.data.client_id) {
            await storage.write(
              STORAGE_KEYS.CLIENT_ID,
              result.data.client_id,
            );
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
          logger.error({ result }, "Mercury pixel: Failed to create session");
          throw new Error(result.message || "Failed to create session");
        }
      } catch (error) {
        logger.error({ error }, "Mercury pixel: Failed to create session");
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
export const trackUnifiedInteraction = async (storage, request) => {
  try {
    if (!storage) {
      throw new Error("Storage is required");
    }

    const interactionData = {
      session_id: request.session_id,
      shop_domain: request.shop_domain,
      extension_type: "mercury", // ✅ Add this required field
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
        logger.error({ response }, "Mercury pixel: Services suspended");
        throw new Error("Services suspended");
      }
      logger.error({ response }, "Mercury pixel: Interaction tracking failed");
      throw new Error(`Interaction tracking failed: ${response.status}`);
    }

    const result = await response.json();

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
export const buildRecommendationMetadata = (params) => {
  const {
    extensionType,
    source = "mercury_checkout_extension",
    cartProductCount,
    recommendationCount,
    recommendations,
    widget = "mercury_recommendation",
    algorithm = "mercury_algorithm",
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
  shopDomain,
  context,
  sessionId,
  customerId,
  productIds,
  metadata,
) => {
  try {
    const recommendations = (productIds || []).map((id, index) => ({
      id,
      position: index + 1,
    }));

    const request = {
      session_id: sessionId,
      shop_domain: shopDomain,
      context,
      interaction_type: "recommendation_viewed",
      customer_id: customerId,
      page_url: null,
      referrer: null,
      metadata: buildRecommendationMetadata({
        extensionType: "mercury",
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
  shopDomain,
  context,
  productId,
  position,
  sessionId,
  customerId,
  metadata,
) => {
  try {
    const request = {
      session_id: sessionId,
      shop_domain: shopDomain,
      context,
      interaction_type: "recommendation_clicked",
      customer_id: customerId,
      product_id: productId,
      page_url: null,
      referrer: null,
      metadata: {
        source: metadata?.source || "mercury_recommendation",
        cart_product_count: metadata?.cart_product_count ?? 0,
        recommendation_count: 1,
        extension_type: "mercury",
        data: {
          product: {
            id: productId,
          },
          position: position,
          type: "recommendation",
          widget: metadata?.widget || "mercury_recommendation",
          algorithm: metadata?.algorithm || "mercury_algorithm",
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

/**
 * Track add to cart action (following Phoenix pattern)
 */
export const trackAddToCart = async (
  storage,
  shopDomain,
  context,
  productId,
  variantId,
  position,
  customerId,
  metadata,
) => {
  try {
    // Get or create session first
    const sessionId = await getOrCreateSession(
      storage,
      shopDomain,
      customerId,
      null,
      null,
      null,
      null,
    );

    const request = {
      session_id: sessionId,
      shop_domain: shopDomain,
      context: context,
      interaction_type: "recommendation_add_to_cart", // Use custom recommendation event
      customer_id: customerId ? String(customerId) : undefined,
      product_id: productId,
      page_url: null,
      referrer: null,
      metadata: {
        ...metadata,
        extension_type: "mercury",
        source: "mercury_checkout_extension",
        // Standard structure expected by adapters
        data: {
          cartLine: {
            merchandise: {
              id: variantId,
              product: {
                id: productId, // Use productId instead of variantId for product_id
              },
            },
            quantity: metadata?.quantity || 1,
          },
          type: "recommendation",
          position: position,
          widget: "mercury_recommendation",
          algorithm: "mercury_algorithm",
          // ✅ Add quantity tracking for proper attribution
          selected_quantity: metadata?.quantity || 1,
        },
      },
    };

    return await trackUnifiedInteraction(storage, request);
  } catch (error) {
    logger.error("Failed to track add to cart:", error);
    return false;
  }
};
