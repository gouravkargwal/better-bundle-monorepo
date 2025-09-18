/**
 * Unified Analytics API Client for BetterBundle Apollo Post-Purchase Extension
 *
 * This client handles all analytics and attribution tracking using the unified analytics system.
 * Designed specifically for Shopify Post-Purchase Extensions with their unique constraints.
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
  | "post_purchase";

export type InteractionType =
  | "page_view"
  | "product_view"
  | "add_to_cart"
  | "remove_from_cart"
  | "search"
  | "purchase"
  | "customer_linked"
  | "submit"
  | "click"
  | "view"
  | "shop_now"
  | "buy_now"
  | "add_to_order"
  | "other";

// Unified Analytics Request Types
export interface UnifiedInteractionRequest {
  session_id: string;
  shop_id: string;
  context: ExtensionContext;
  interaction_type: InteractionType;
  customer_id?: string;
  product_id?: string;
  collection_id?: string;
  search_query?: string;
  page_url?: string;
  referrer?: string;
  time_on_page?: number;
  scroll_depth?: number;
  metadata: Record<string, any>;
}

export interface UnifiedSessionRequest {
  shop_id: string;
  customer_id?: string;
  browser_session_id?: string;
  user_agent?: string;
  ip_address?: string;
  referrer?: string;
  page_url?: string;
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
    [key: string]: any;
  };
}

class ApolloAnalyticsClient {
  private baseUrl: string;
  private currentSessionId: string | null = null;
  private sessionExpiresAt: number | null = null;

  constructor() {
    // Use the unified analytics service URL
    this.baseUrl = "https://d242bda5e5c7.ngrok-free.app";
  }

  /**
   * Get or create a session for Apollo tracking
   */
  async getOrCreateSession(
    shopId: string,
    customerId?: string,
  ): Promise<string> {
    // Check if we have a valid session
    if (
      this.currentSessionId &&
      this.sessionExpiresAt &&
      Date.now() < this.sessionExpiresAt
    ) {
      return this.currentSessionId;
    }

    try {
      const url = `${this.baseUrl}/api/apollo/get-or-create-session`;

      const payload: UnifiedSessionRequest = {
        shop_id: shopId,
        customer_id: customerId || undefined,
        browser_session_id: this.getBrowserSessionId(),
        user_agent: navigator.userAgent,
        ip_address: undefined, // Will be detected server-side
        referrer: document.referrer,
        page_url: window.location.href,
      };

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
        this.currentSessionId = sessionId;
        // Set session to expire 30 minutes from now (server handles actual expiration)
        this.sessionExpiresAt = Date.now() + 30 * 60 * 1000;

        console.log("🔄 Apollo session created/retrieved:", sessionId);
        return sessionId;
      } else {
        throw new Error(result.message || "Failed to create session");
      }
    } catch (error) {
      console.error("💥 Apollo session creation error:", error);
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
      // Get or create session first
      const sessionId = await this.getOrCreateSession(
        request.shop_id,
        request.customer_id,
      );

      // Update request with session ID
      const interactionData = {
        ...request,
        session_id: sessionId,
      };

      // Send to unified analytics endpoint
      const url = `${this.baseUrl}/api/apollo/track-interaction`;

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(interactionData),
        keepalive: true,
      });

      if (!response.ok) {
        throw new Error(`Interaction tracking failed: ${response.status}`);
      }

      const result: UnifiedResponse = await response.json();

      if (result.success) {
        console.log(
          "✅ Apollo interaction tracked:",
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
   * Track post-purchase recommendation view
   */
  async trackRecommendationView(
    shopId: string,
    customerId?: string,
    orderId?: string,
    productIds?: string[],
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    try {
      const request: UnifiedInteractionRequest = {
        session_id: "", // Will be set by trackUnifiedInteraction
        shop_id: shopId,
        context: "post_purchase",
        interaction_type: "view",
        customer_id: customerId,
        page_url: window.location.href,
        referrer: document.referrer,
        metadata: {
          ...metadata,
          extension_type: "apollo",
          product_ids: productIds,
          recommendation_count: productIds?.length || 0,
          order_id: orderId,
          source: "apollo_post_purchase",
        },
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      console.error("Failed to track recommendation view:", error);
      return false;
    }
  }

  /**
   * Track post-purchase recommendation click
   */
  async trackRecommendationClick(
    shopId: string,
    productId: string,
    position: number,
    customerId?: string,
    orderId?: string,
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    try {
      const request: UnifiedInteractionRequest = {
        session_id: "", // Will be set by trackUnifiedInteraction
        shop_id: shopId,
        context: "post_purchase",
        interaction_type: "click",
        customer_id: customerId,
        product_id: productId,
        page_url: window.location.href,
        referrer: document.referrer,
        metadata: {
          ...metadata,
          extension_type: "apollo",
          position,
          order_id: orderId,
          source: "apollo_post_purchase",
          interaction_type: "recommendation_click",
        },
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      console.error("Failed to track recommendation click:", error);
      return false;
    }
  }

  /**
   * Track add to order action
   */
  async trackAddToOrder(
    shopId: string,
    productId: string,
    variantId: string,
    position: number,
    customerId?: string,
    orderId?: string,
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    try {
      const request: UnifiedInteractionRequest = {
        session_id: "", // Will be set by trackUnifiedInteraction
        shop_id: shopId,
        context: "post_purchase",
        interaction_type: "add_to_order",
        customer_id: customerId,
        product_id: productId,
        page_url: window.location.href,
        referrer: document.referrer,
        metadata: {
          ...metadata,
          extension_type: "apollo",
          variant_id: variantId,
          position,
          order_id: orderId,
          source: "apollo_post_purchase",
          interaction_type: "add_to_order",
        },
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      console.error("Failed to track add to order:", error);
      return false;
    }
  }

  /**
   * Get unified browser session ID (shared across all extensions)
   */
  private getBrowserSessionId(): string {
    let sessionId = sessionStorage.getItem("unified_browser_session_id");
    if (!sessionId) {
      sessionId =
        "unified_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
      sessionStorage.setItem("unified_browser_session_id", sessionId);
    }
    return sessionId;
  }
}

// Default instance
export const apolloAnalytics = new ApolloAnalyticsClient();
