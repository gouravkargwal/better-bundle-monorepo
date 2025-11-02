import { BACKEND_URL } from "../config/constants";
import type {
  InteractionType,
  UnifiedInteractionRequest,
  UnifiedResponse,
} from "../types";
import { logger } from "../utils/logger";
import { makeAuthenticatedRequest } from "../utils/jwt";

/**
 * Track interaction using unified analytics (internal helper)
 */
const trackInteraction = async (
  sessionId: string,
  shopDomain: string,
  interactionType: InteractionType,
  productId?: string,
  customerId?: string,
  metadata?: Record<string, any>,
): Promise<boolean> => {
  try {
    const url = `${BACKEND_URL}/api/interaction/track`;

    const request: UnifiedInteractionRequest = {
      session_id: sessionId,
      shop_domain: shopDomain,
      extension_type: "apollo", // Required field for backend
      context: "post_purchase",
      interaction_type: interactionType,
      product_id: productId ? String(productId) : undefined,
      customer_id: customerId ? String(customerId) : undefined,
      metadata: metadata || {},
    };

    const response = await makeAuthenticatedRequest(url, {
      method: "POST",
      body: JSON.stringify(request),
      keepalive: true,
      shopDomain: shopDomain,
      customerId: customerId,
    });

    if (!response.ok) {
      if (response.status === 403) {
        throw new Error("Services suspended");
      }
      logger.error(
        {
          error: new Error(`Interaction tracking failed: ${response.status}`),
          shop_domain: shopDomain,
          interactionType,
          productId,
          customerId,
          metadata,
        },
        "Interaction tracking failed",
      );
      throw new Error(`Interaction tracking failed: ${response.status}`);
    }

    const result: UnifiedResponse = await response.json();

    if (result.success) {
      if (result.session_recovery) {
        localStorage.setItem(
          "unified_session_id",
          result.session_recovery.new_session_id,
        );
      }
      return true;
    } else {
      logger.error(
        {
          error: new Error(result.message || "Failed to track interaction"),
          shop_domain: shopDomain,
          interactionType,
          productId,
          customerId,
          metadata,
        },
        "Failed to track interaction",
      );
      throw new Error(result.message || "Failed to track interaction");
    }
  } catch (error) {
    logger.error(
      {
        error: error instanceof Error ? error.message : String(error),
        shop_domain: shopDomain,
        interactionType,
        productId,
        customerId,
        metadata,
      },
      "Interaction tracking error",
    );
    return false;
  }
};

/**
 * Track recommendation view (when recommendation is displayed)
 */
export const trackRecommendationView = async (
  shopDomain: string,
  sessionId: string,
  productId: string,
  position: number,
  customerId: string,
  metadata?: Record<string, any>,
): Promise<boolean> => {
  return trackInteraction(
    sessionId,
    shopDomain,
    "recommendation_viewed",
    productId,
    customerId,
    {
      extension_type: "apollo",
      source: "apollo_post_purchase",
      data: {
        product: {
          id: productId,
          title: metadata?.product_title || "",
          price: metadata?.product_price || 0,
          type: metadata?.product_type || "",
          vendor: metadata?.product_vendor || "",
          url: metadata?.product_url || "",
        },
        type: "recommendation",
        position: position,
        widget: "apollo_recommendation",
        algorithm: "apollo_algorithm",
        confidence: metadata?.recommendation_confidence || 0.0,
        pageUrl: metadata?.page_url || "",
      },
      ...metadata,
    },
  );
};

/**
 * Track recommendation click (when user clicks on a recommendation)
 */
export const trackRecommendationClick = async (
  shopDomain: string,
  sessionId: string,
  productId: string,
  position: number,
  customerId: string,
  metadata?: Record<string, any>,
): Promise<boolean> => {
  return trackInteraction(
    sessionId,
    shopDomain,
    "recommendation_clicked",
    productId,
    customerId,
    {
      extension_type: "apollo",
      source: "apollo_post_purchase",
      data: {
        product: {
          id: productId,
          title: metadata?.product_title || "",
          price: metadata?.product_price || 0,
          type: metadata?.product_type || "",
          vendor: metadata?.product_vendor || "",
          url: metadata?.product_url || "",
        },
        type: "recommendation",
        position: position,
        widget: "apollo_recommendation",
        algorithm: "apollo_algorithm",
        confidence: metadata?.recommendation_confidence || 0.0,
        pageUrl: metadata?.page_url || "",
      },
      ...metadata,
    },
  );
};

/**
 * Track add to order (when user adds a recommendation to their order)
 */
export const trackAddToOrder = async (
  shopDomain: string,
  sessionId: string,
  productId: string,
  variantId: string,
  position: number,
  customerId: string,
  metadata?: Record<string, any>,
): Promise<boolean> => {
  return trackInteraction(
    sessionId,
    shopDomain,
    "recommendation_add_to_cart",
    productId,
    customerId,
    {
      extension_type: "apollo",
      source: "apollo_post_purchase",
      data: {
        cartLine: {
          merchandise: {
            id: variantId,
            product: {
              id: productId,
            },
          },
          quantity: metadata?.quantity || 1,
        },
        type: "recommendation",
        position: position,
        widget: "apollo_recommendation",
        algorithm: "apollo_algorithm",
      },
      action: "add_to_order_success",
      changeset_applied: true,
      ...metadata,
    },
  );
};

/**
 * Track recommendation decline (when user dismisses a recommendation)
 */
export const trackRecommendationDecline = async (
  shopDomain: string,
  sessionId: string,
  productId: string,
  position: number,
  customerId: string,
  productData?: any,
  metadata?: Record<string, any>,
): Promise<boolean> => {
  return trackInteraction(
    sessionId,
    shopDomain,
    "recommendation_declined",
    productId,
    customerId,
    {
      extension_type: "apollo",
      source: "apollo_post_purchase",
      data: {
        product: {
          id: productId,
          title: productData?.title || "",
          price: productData?.price?.amount || 0,
          type: productData?.product_type || "",
          vendor: productData?.vendor || "",
        },
        type: "recommendation",
        position: position,
        widget: "apollo_recommendation",
        algorithm: "apollo_algorithm",
        confidence: productData?.score || 0.0,
        decline_reason: metadata?.decline_reason || "user_declined",
      },
      action: "recommendation_declined",
      ...metadata,
    },
  );
};
