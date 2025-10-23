/**
 * Apollo Analytics API Client - Fixed Version
 *
 * This client handles all analytics tracking for the Apollo Post-Purchase extension.
 * It properly integrates with the unified analytics backend system.
 *
 * Key Features:
 * - Session management with the unified system
 * - Recommendation view tracking (when recommendations are displayed)
 * - Recommendation click tracking (when "Add to Order" is clicked)
 * - Add to order success tracking (when product is successfully added)
 * - Proper error handling and retry logic
 */

// ============================================================================
// TYPES
// ============================================================================

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
  | "post_purchase";

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
  | "recommendation_ready"
  | "recommendation_viewed"
  | "recommendation_clicked"
  | "recommendation_add_to_cart"
  | "recommendation_declined";

interface UnifiedInteractionRequest {
  session_id: string;
  shop_domain: string;
  context: ExtensionContext;
  interaction_type: InteractionType;
  customer_id?: string;
  product_id?: string;
  collection_id?: string;
  search_query?: string;
  page_url?: string;
  referrer?: string;
  metadata: Record<string, any>;
}

interface UnifiedResponse {
  success: boolean;
  message: string;
  data?: {
    session_id?: string;
    interaction_id?: string;
    [key: string]: any;
  };
}

// ============================================================================
// APOLLO ANALYTICS CLIENT
// ============================================================================

class ApolloAnalyticsClient {
  private baseUrl: string;

  constructor() {
    // Use the unified analytics service URL
    this.baseUrl = process.env.BACKEND_URL;
  }

  /**
   * Track interaction using unified analytics
   * This is the core method that all other tracking methods use
   */
  private async trackInteraction(
    sessionId: string,
    shopDomain: string,
    interactionType: InteractionType,
    productId?: string,
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    try {
      const url = `${this.baseUrl}/api/apollo/track-interaction`;

      const request: UnifiedInteractionRequest = {
        session_id: sessionId,
        shop_domain: shopDomain,
        context: "post_purchase",
        interaction_type: interactionType,
        product_id: productId ? String(productId) : undefined, // ✅ Ensure string
        metadata: metadata || {},
      };

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
        keepalive: true, // Ensures request completes even if page unloads
      });

      if (!response.ok) {
        throw new Error(`Interaction tracking failed: ${response.status}`);
      }

      const result: UnifiedResponse = await response.json();

      if (result.success) {
        console.log(
          "✅ Apollo interaction tracked:",
          interactionType,
          result.data?.interaction_id,
        );
        return true;
      } else {
        throw new Error(result.message || "Failed to track interaction");
      }
    } catch (error) {
      console.error("💥 Apollo interaction tracking error:", error);
      return false;
    }
  }

  /**
   * Track recommendation view
   * Called when recommendations are displayed to the user
   *
   * @param shopDomain - Shop domain (e.g., "mystore.myshopify.com")
   * @param sessionId - Session ID from the combined API response
   * @param productId - Product ID being viewed
   * @param position - Position in the recommendation list (1-indexed)
   * @param metadata - Additional tracking data
   */
  async trackRecommendationView(
    shopDomain: string,
    sessionId: string,
    productId: string,
    position: number,
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    return this.trackInteraction(
      sessionId,
      shopDomain,
      "recommendation_viewed",
      productId,
      {
        extension_type: "apollo",
        source: "apollo_post_purchase",
        // Standard structure expected by adapters
        data: {
          product: {
            id: productId,
          },
          type: "recommendation",
          position: position,
          widget: "apollo_recommendation",
          algorithm: "apollo_algorithm",
        },
        ...metadata,
      },
    );
  }

  /**
   * Track recommendation click
   * Called when user clicks "Add to Order" button
   *
   * @param shopDomain - Shop domain (e.g., "mystore.myshopify.com")
   * @param sessionId - Session ID from the combined API response
   * @param productId - Product ID being clicked
   * @param position - Position in the recommendation list (1-indexed)
   * @param metadata - Additional tracking data (variant_id, price, etc.)
   */
  async trackRecommendationClick(
    shopDomain: string,
    sessionId: string,
    productId: string,
    position: number,
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    return this.trackInteraction(
      sessionId,
      shopDomain,
      "recommendation_clicked",
      productId,
      {
        extension_type: "apollo",
        source: "apollo_post_purchase",
        // Standard structure expected by adapters
        data: {
          product: {
            id: productId,
          },
          type: "recommendation",
          position: position,
          widget: "apollo_recommendation",
          algorithm: "apollo_algorithm",
        },
        ...metadata,
      },
    );
  }

  /**
   * Track successful add to order
   * Called after product is successfully added via changeset
   *
   * @param shopDomain - Shop domain (e.g., "mystore.myshopify.com")
   * @param sessionId - Session ID from the combined API response
   * @param productId - Product ID that was added
   * @param variantId - Variant ID that was added
   * @param position - Position in the recommendation list (1-indexed)
   * @param metadata - Additional tracking data (price, new_total, etc.)
   */
  async trackAddToOrder(
    shopDomain: string,
    sessionId: string,
    productId: string,
    variantId: string,
    position: number,
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    return this.trackInteraction(
      sessionId,
      shopDomain,
      "recommendation_add_to_cart",
      productId,
      {
        extension_type: "apollo",
        source: "apollo_post_purchase",
        // Standard structure expected by adapters
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
  }

  /**
   * Track recommendation decline
   * Called when user declines/rejects a recommendation
   *
   * @param shopDomain - Shop domain (e.g., "mystore.myshopify.com")
   * @param sessionId - Session ID from the combined API response
   * @param productId - Product ID that was declined
   * @param position - Position in the recommendation list (1-indexed)
   * @param metadata - Additional tracking data (reason, etc.)
   */
  async trackRecommendationDecline(
    shopDomain: string,
    sessionId: string,
    productId: string,
    position: number,
    productData?: any,
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    return this.trackInteraction(
      sessionId,
      shopDomain,
      "recommendation_declined",
      productId,
      {
        extension_type: "apollo",
        source: "apollo_post_purchase",
        // Streamlined metadata - only what Gorse actually uses
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
  }
}

// ============================================================================
// EXPORT DEFAULT INSTANCE
// ============================================================================

export const apolloAnalytics = new ApolloAnalyticsClient();
