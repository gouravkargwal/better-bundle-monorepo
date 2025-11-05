import { BACKEND_URL } from "../config/constants";
import { logger } from "../utils/logger";
import { makeAuthenticatedRequest } from "../utils/jwt";

export function buildMercuryMetadata(
  checkoutStep,
  cartValue,
  cartItems,
) {
  return {
    mercury_checkout: true,
    checkout_type: "one_page",
    checkout_step: checkoutStep,
    cart_value: cartValue,
    cart_items: cartItems,
    block: "checkout.order-summary.render", // Primary placement for one-page checkout
  };
}

/**
 * Get recommendations
 */
export const getRecommendations = async (storage, request) => {
  try {
    if (!storage) {
      throw new Error("Storage is required");
    }

    // Ensure Mercury uses single checkout context
    const mercuryRequest = {
      ...request,
      context: "checkout_page", // Force single context for Mercury
      metadata: {
        ...request.metadata,
        ...buildMercuryMetadata(
          request.checkout_step,
          request.cart_value,
          request.cart_items,
        ),
      },
    };

    // ✅ Use makeAuthenticatedRequest for automatic token refresh
    // customerId (user_id) can be null for guest checkouts
    const response = await makeAuthenticatedRequest(
      storage,
      `${BACKEND_URL}/api/v1/recommendations`,
      {
        method: "POST",
        shopDomain: request.shop_domain,
        customerId: request.user_id || undefined, // Pass undefined instead of null
        body: JSON.stringify(mercuryRequest),
      }
    );

    if (!response.ok) {
      if (response.status === 403) {
        throw new Error("Services suspended");
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    logger.error("Failed to fetch Mercury recommendations:", error);
    throw error;
  }
};
