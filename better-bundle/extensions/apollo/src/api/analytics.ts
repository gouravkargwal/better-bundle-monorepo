import { BACKEND_URL } from "../config/constants";
import type { InteractionType } from "../types";
import { logger } from "../utils/logger";
import { makeAuthenticatedRequest } from "../utils/jwt";

/**
 * Formerly posted every view, click and decline to `/api/interaction/track`.
 *
 * That endpoint went with the behaviour-tracking pipeline. Nothing replaces it:
 * the impression row is written server-side the moment recommendations are
 * served, so a client-side view report added nothing, and terminal outcomes go
 * through `recordOfferOutcome` below.
 *
 * Kept as a no-op rather than deleted because App.tsx calls the wrappers from a
 * dozen places, and a silent no-op is safer here than a partly-rewired render
 * path on a surface that only fires once per order.
 */
const trackInteraction = async (
  _sessionId: string,
  _shopDomain: string,
  _interactionType: InteractionType,
  _productId?: string,
  _customerId?: string,
  _metadata?: Record<string, any>,
): Promise<boolean> => {
  return true;
};

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

/**
 * Record offer outcome for incrementality tracking.
 * Called when user accepts or declines an offer.
 */
export const recordOfferOutcome = async (
  impressionId: string,
  outcome: "accepted" | "declined" | "ignored",
  revenueAdded?: number,
): Promise<boolean> => {
  try {
    const url = `${BACKEND_URL}/api/interaction/outcome`;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        impression_id: impressionId,
        outcome,
        ...(revenueAdded !== undefined ? { revenue_added: revenueAdded } : {}),
      }),
      keepalive: true,
    });
    return response.ok;
  } catch (error) {
    logger.error({ error }, "Failed to record offer outcome");
    return false;
  }
};
