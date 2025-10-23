/**
 * Unified Analytics API Client for BetterBundle Venus Extension
 *
 * This client handles all analytics and attribution tracking using the unified analytics system.
 * Follows proper separation of concerns and single responsibility principle.
 */

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
}

class AnalyticsApiClient {
  private baseUrl: string;
  constructor() {
    this.baseUrl = process.env.BACKEND_URL;
  }

  async getOrCreateSession(
    shopDomain: string,
    customerId: string,
  ): Promise<string> {
    try {
      const url = `${this.baseUrl}/api/venus/get-or-create-session`;
      const payload: UnifiedSessionRequest = {
        shop_domain: shopDomain,
        customer_id: customerId,
        user_agent: navigator.userAgent,
        ip_address: undefined,
        referrer: undefined,
      };

      console.log("🌐 Venus: Creating session with:", {
        shop_domain: shopDomain,
        customer_id: customerId,
      });

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

      const result: UnifiedResponse = await response.json();

      if (result.success && result.data && result.data.session_id) {
        const sessionId = result.data.session_id;
        console.log("✅ Venus: Session created/retrieved:", sessionId);
        return sessionId;
      } else {
        throw new Error(result.message || "Failed to create session");
      }
    } catch (error) {
      console.error("💥 Venus: Session creation error:", error);
      throw error;
    }
  }

  /**
   * Track interaction using unified analytics
   */
  async trackUnifiedInteraction(
    request: UnifiedInteractionRequest,
  ): Promise<boolean> {
    try {
      const url = `${this.baseUrl}/api/venus/track-interaction`;
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
        keepalive: true,
      });

      if (!response.ok) {
        throw new Error(`Interaction tracking failed: ${response.status}`);
      }

      const result: UnifiedResponse = await response.json();

      if (result.success) {
        console.log(
          "✅ Venus interaction tracked:",
          result.data?.interaction_id,
        );
        return true;
      } else {
        throw new Error(result.message || "Failed to track interaction");
      }
    } catch (error) {
      console.error("💥 Venus interaction tracking error:", error);
      return false;
    }
  }

  private buildRecommendationMetadata(params: {
    extensionType: "venus";
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
  ): Promise<boolean> {
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
          extensionType: "venus",
          recommendationCount: recommendations.length,
          recommendations,
          cartProductCount: metadata?.cart_product_count,
          extra: metadata,
        }),
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      console.error("Failed to track recommendation view:", error);
      return false;
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
  ): Promise<boolean> {
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

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      console.error("Failed to track recommendation click:", error);
      return false;
    }
  }
}

// Default instance
export const analyticsApi = new AnalyticsApiClient();
