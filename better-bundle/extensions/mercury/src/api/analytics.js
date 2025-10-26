import { BACKEND_URL } from "../constant";
import { logger } from "../utils/logger";

class AnalyticsApiClient {
  constructor() {
    this.baseUrl = BACKEND_URL;
    this.jwtManager = null;
    this.logger = logger;
  }

  setJWTManager(jwtManager) {
    this.jwtManager = jwtManager;
  }

  async getOrCreateSession(shopDomain, customerId) {
    try {
      if (!this.jwtManager) {
        throw new Error("JWT Manager not initialized");
      }

      const url = `${this.baseUrl}/api/mercury/get-or-create-session`;
      const payload = {
        shop_domain: shopDomain,
        customer_id: customerId,
        user_agent: navigator.userAgent,
        ip_address: undefined,
        referrer: undefined,
      };

      const response = await this.jwtManager.makeAuthenticatedRequest(url, {
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
        throw new Error(`Session creation failed: ${response.status}`);
      }

      const result = await response.json();

      if (result.success && result.data && result.data.session_id) {
        const sessionId = result.data.session_id;
        return sessionId;
      } else {
        throw new Error(result.message || "Failed to create session");
      }
    } catch (error) {
      this.logger.error("Session creation error:", error);
      throw error;
    }
  }

  /**
   * Track interaction using unified analytics
   */
  async trackUnifiedInteraction(request) {
    try {
      if (!this.jwtManager) {
        throw new Error("JWT Manager not initialized");
      }

      const url = `${this.baseUrl}/api/mercury/track-interaction`;
      const response = await this.jwtManager.makeAuthenticatedRequest(url, {
        method: "POST",
        body: JSON.stringify(request),
        keepalive: true,
        shopDomain: request.shop_domain,
        customerId: request.customer_id,
      });

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error("Services suspended");
        }
        throw new Error(`Interaction tracking failed: ${response.status}`);
      }

      const result = await response.json();

      if (result.success) {
        // Handle session recovery if it occurred
        if (result.session_recovery) {
          // Update stored session ID with the new one (unified with other extensions)
          sessionStorage.setItem(
            "unified_session_id",
            result.session_recovery.new_session_id,
          );
        }

        return true;
      } else {
        throw new Error(result.message || "Failed to track interaction");
      }
    } catch (error) {
      this.logger.error("Interaction tracking error:", error);
      return false;
    }
  }

  buildRecommendationMetadata(params) {
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
  }

  /**
   * Track recommendation view (when recommendations are displayed)
   */
  async trackRecommendationView(
    shopDomain,
    context,
    sessionId,
    customerId,
    productIds,
    metadata,
  ) {
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
        metadata: this.buildRecommendationMetadata({
          extensionType: "mercury",
          recommendationCount: recommendations.length,
          recommendations,
          cartProductCount: metadata?.cart_product_count,
          extra: metadata,
        }),
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      this.logger.error("Failed to track recommendation view:", error);
      return false;
    }
  }

  /**
   * Track recommendation click (when user clicks on a recommendation)
   */
  async trackRecommendationClick(
    shopDomain,
    context,
    productId,
    position,
    sessionId,
    customerId,
    metadata,
  ) {
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

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      this.logger.error("Failed to track recommendation click:", error);
      return false;
    }
  }

  /**
   * Track add to cart action (following Phoenix pattern)
   */
  async trackAddToCart(shopDomain, context, productId, variantId, position, customerId, metadata) {
    try {
      const request = {
        session_id: "", // Will be set by trackUnifiedInteraction
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
                  id: productId  // Use productId instead of variantId for product_id
                }
              },
              quantity: metadata?.quantity || 1
            },
            type: "recommendation",
            position: position,
            widget: "mercury_recommendation",
            algorithm: "mercury_algorithm",
            // ✅ Add quantity tracking for proper attribution
            selected_quantity: metadata?.quantity || 1
          }
        },
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      this.logger.error("Failed to track add to cart:", error);
      return false;
    }
  }
}

// Default instance
export const analyticsApi = new AnalyticsApiClient();