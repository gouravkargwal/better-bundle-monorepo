import { BACKEND_URL } from "../config/constants";
import type { ProductRecommendation, CombinedAPIResponse } from "../types";
import { logger } from "../utils/logger";
import { makeAuthenticatedRequest } from "../utils/jwt";

// Module-level cache to prevent duplicate API calls for the same order
const resultCache = new Map<
  string,
  {
    sessionId: string;
    recommendations: ProductRecommendation[];
    success: boolean;
    error?: string;
  }
>();

// Module-level promise to prevent concurrent session creation calls for the same order
const sessionCreationPromises = new Map<
  string,
  Promise<{
    sessionId: string;
    recommendations: ProductRecommendation[];
    success: boolean;
    error?: string;
  }>
>();

/**
 * Get session and recommendations
 */
export const getSessionAndRecommendations = async (
  shopDomain: string,
  customerId?: string,
  orderId?: string,
  purchasedProductIds?: string[],
  limit: number = 3,
  metadata?: Record<string, any>,
): Promise<{
  sessionId: string;
  recommendations: ProductRecommendation[];
  success: boolean;
  error?: string;
}> => {
  // Create cache key from orderId (most important) and shopDomain
  const cacheKey = `${shopDomain}:${orderId || "no-order"}`;

  // Check if we already have a cached result for this order
  if (resultCache.has(cacheKey)) {
    const cachedResult = resultCache.get(cacheKey)!;
    logger.info(
      `Apollo: Reusing cached result for order ${orderId}, skipping API call`,
    );
    return cachedResult;
  }

  // Prevent concurrent calls for the same order to avoid race conditions on backend
  const existingPromise = sessionCreationPromises.get(cacheKey);
  if (existingPromise) {
    logger.warn(
      `Apollo: Concurrent session creation detected for order ${orderId}, reusing existing promise`,
    );
    return await existingPromise;
  }

  const promise = (async () => {
    try {
      const url = `${BACKEND_URL}/api/session/get-session-and-recommendations`;

      const payload = {
        shop_domain: shopDomain,
        customer_id: customerId ? String(customerId) : null,
        browser_session_id: undefined,
        client_id: undefined,
        user_agent:
          typeof navigator !== "undefined" ? navigator.userAgent : undefined,
        ip_address: undefined,
        referrer:
          typeof document !== "undefined" ? document.referrer : undefined,
        page_url:
          typeof window !== "undefined" ? window.location.href : undefined,

        // Recommendation fields
        order_id: orderId ? String(orderId) : null,
        purchased_products: purchasedProductIds || [],
        limit: Math.min(Math.max(limit, 1), 3),
        extension_type: "apollo",
        // Additional metadata
        metadata: {
          source: "apollo_post_purchase",
          ...metadata,
        },
      };

      const response = await makeAuthenticatedRequest(url, {
        method: "POST",
        body: JSON.stringify(payload),
        keepalive: true,
        shopDomain: shopDomain,
        customerId: customerId,
      });

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error("Services suspended");
        }
        const errorText = await response.text();
        logger.error(
          {
            error: new Error(
              `API call failed with status ${response.status}: ${errorText}`,
            ),
            shop_domain: shopDomain,
            customerId,
            orderId,
            purchasedProductIds,
          },
          "Failed to get session and recommendations",
        );
        throw new Error(
          `API call failed with status ${response.status}: ${errorText}`,
        );
      }

      const result: CombinedAPIResponse = await response.json();

      if (!result.success) {
        logger.error(
          {
            error: new Error(result.message || "API returned success: false"),
            shop_domain: shopDomain,
            customerId,
            orderId,
            purchasedProductIds,
          },
          "Failed to get session and recommendations",
        );
        throw new Error(result.message || "API returned success: false");
      }

      if (!result.session_data || !result.session_data.session_id) {
        logger.error(
          {
            error: new Error("Invalid response: missing session data"),
            shop_domain: shopDomain,
            customerId,
            orderId,
            purchasedProductIds,
          },
          "Invalid response: missing session data",
        );
        throw new Error("Invalid response: missing session data");
      }

      const finalResult = {
        sessionId: result.session_data.session_id,
        recommendations: result.recommendations || [],
        success: true,
      };

      // Cache the successful result
      resultCache.set(cacheKey, finalResult);
      return finalResult;
    } catch (error) {
      logger.error(
        {
          error: error instanceof Error ? error.message : String(error),
          shop_domain: shopDomain,
          customerId,
          orderId,
          purchasedProductIds,
        },
        "Failed to get session and recommendations",
      );

      const errorResult = {
        sessionId: "",
        recommendations: [],
        success: false,
        error:
          error instanceof Error ? error.message : "Unknown error occurred",
      };

      // Also cache error results to prevent retrying failed calls
      resultCache.set(cacheKey, errorResult);
      return errorResult;
    } finally {
      // Remove the promise from the map after completion
      sessionCreationPromises.delete(cacheKey);
    }
  })();

  // Store the promise in the map
  sessionCreationPromises.set(cacheKey, promise);

  return await promise;
};
