/**
 * Unified Analytics API Client for BetterBundle Venus Extension
 *
 * This client handles all analytics and attribution tracking using the unified analytics system.
 * Follows proper separation of concerns and single responsibility principle.
 */

import { BACKEND_URL } from "../utils/constant";
import { type Logger, logger } from "../utils/logger";

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

export interface UnifiedSessionRequest {
  shop_domain: string;
  customer_id?: string;
  user_agent?: string;
  ip_address?: string;
  referrer?: string;
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

class AnalyticsApiClient {
  private baseUrl: string;
  private logger: Logger;
  private makeAuthenticatedRequest:
    | ((url: string, options?: RequestInit) => Promise<Response>)
    | null = null;

  constructor() {
    this.baseUrl = BACKEND_URL;
    this.logger = logger;
  }

  /**
   * Set JWT authentication function
   */
  setJWT(
    makeAuthenticatedRequest: (
      url: string,
      options?: RequestInit,
    ) => Promise<Response>,
  ): void {
    this.makeAuthenticatedRequest = makeAuthenticatedRequest;
  }

  /**
   * Get current session ID from sessionStorage
   * Note: This method is deprecated - session management is handled by the calling component
   */
  getCurrentSessionId(): string | null {
    // Session management is handled by the calling component using Shopify storage API
    return null;
  }

  async getOrCreateSession(
    shopDomain: string,
    customerId: string,
  ): Promise<string> {
    try {
      if (!this.makeAuthenticatedRequest) {
        throw new Error("JWT authentication not initialized");
      }

      const url = `${this.baseUrl}/api/phoenix/get-or-create-session`;
      const payload: UnifiedSessionRequest = {
        shop_domain: shopDomain,
        customer_id: customerId,
        user_agent: navigator.userAgent,
        ip_address: undefined,
        referrer: undefined,
      };

      // Use JWT authentication for the request
      const response = await this.makeAuthenticatedRequest(url, {
        method: "POST",
        body: JSON.stringify(payload),
        keepalive: true,
      });

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error("Services suspended");
        }
        throw new Error(`Session creation failed: ${response.status}`);
      }

      const result: UnifiedResponse = await response.json();

      if (result.success && result.data && result.data.session_id) {
        const sessionId = result.data.session_id;
        return sessionId;
      } else {
        this.logger.error(
          {
            message: result.message,
            shop_domain: shopDomain,
          },
          "Failed to create session",
        );
        throw new Error(result.message || "Failed to create session");
      }
    } catch (error) {
      this.logger.error(
        {
          error: error instanceof Error ? error.message : String(error),
          shop_domain: shopDomain,
        },
        "Session creation error",
      );
      throw error;
    }
  }

  /**
   * Track interaction using unified analytics
   */
  async trackUnifiedInteraction(
    request: UnifiedInteractionRequest,
  ): Promise<{ success: boolean; sessionRecovery?: any }> {
    try {
      if (!this.makeAuthenticatedRequest) {
        return { success: false };
      }

      const url = `${this.baseUrl}/api/phoenix/track-interaction`;
      const response = await this.makeAuthenticatedRequest(url, {
        method: "POST",
        body: JSON.stringify(request),
        keepalive: true,
      });

      if (!response.ok) {
        throw new Error(`Interaction tracking failed: ${response.status}`);
      }

      const result: UnifiedResponse = await response.json();

      if (result.success) {
        return {
          success: true,
          sessionRecovery: result.session_recovery || null,
        };
      } else {
        this.logger.error(
          {
            message: result.message,
            shop_domain: request.shop_domain,
          },
          "Failed to track interaction",
        );
        throw new Error(result.message || "Failed to track interaction");
      }
    } catch (error) {
      this.logger.error(
        {
          error: error instanceof Error ? error.message : String(error),
          shop_domain: request.shop_domain,
        },
        "Interaction tracking error",
      );
      return { success: false };
    }
  }

  private buildRecommendationMetadata(params: {
    extensionType: "phoenix";
    source?: string;
    cartProductCount?: number;
    recommendationCount: number;
    recommendations: { id: string; position: number }[];
    widget?: string;
    algorithm?: string;
    // Any additional fields provided by caller should still be preserved
    extra?: Record<string, any>;
  }): Record<string, any> {
    const {
      extensionType,
      source = "phoenix_theme_extension",
      cartProductCount,
      recommendationCount,
      recommendations,
      widget = "phoenix_recommendation",
      algorithm = "phoenix_algorithm",
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
    shopDomain: string,
    context: ExtensionContext,
    sessionId: string,
    customerId?: string,
    productIds?: string[],
    metadata?: Record<string, any>,
  ): Promise<{ success: boolean; sessionRecovery?: any }> {
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
        metadata: this.buildRecommendationMetadata({
          extensionType: "phoenix",
          recommendationCount: recommendations.length,
          recommendations,
          cartProductCount: metadata?.cart_product_count,
          extra: metadata,
        }),
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      this.logger.error(
        {
          error: error instanceof Error ? error.message : String(error),
          shop_domain: shopDomain,
        },
        "Failed to track recommendation view",
      );
      return { success: false };
    }
  }

  /**
   * Track recommendation click (when user clicks on a recommendation)
   */
  async trackRecommendationClick(
    shopDomain: string,
    context: ExtensionContext,
    productId: string,
    position: number,
    sessionId: string,
    customerId?: string,
    metadata?: Record<string, any>,
  ): Promise<{ success: boolean; sessionRecovery?: any }> {
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
          source: metadata?.source || "phoenix_recommendation",
          cart_product_count: metadata?.cart_product_count ?? 0,
          recommendation_count: 1,
          extension_type: "phoenix",
          data: {
            product: {
              id: productId,
            },
            position: position,
            type: "recommendation",
            widget: metadata?.widget || "phoenix_recommendation",
            algorithm: metadata?.algorithm || "phoenix_algorithm",
          },
          ...metadata,
        },
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      this.logger.error(
        {
          error: error instanceof Error ? error.message : String(error),
          shop_domain: shopDomain,
        },
        "Failed to track recommendation click",
      );
      return { success: false };
    }
  }
}

// Default instance
export const analyticsApi = new AnalyticsApiClient();
