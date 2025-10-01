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
  client_id?: string; // ✅ NEW
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
    client_id?: string; // ✅ NEW
    [key: string]: any;
  };
}

class ApolloAnalyticsClient {
  private baseUrl: string;
  private currentSessionId: string | null = null;
  private sessionExpiresAt: number | null = null;
  private clientId: string | null = null; // ✅ NEW

  constructor() {
    // Use the unified analytics service URL
    this.baseUrl = "https://c5da58a2ed7b.ngrok-free.app";
  }

  /**
   * Get or create a session for Apollo tracking
   */
  async getOrCreateSession(
    shopId: string,
    customerId?: string,
  ): Promise<string> {
    // ✅ STEP 1: Try to get client_id from sessionStorage
    if (!this.clientId) {
      this.clientId = this.getClientIdFromStorage();
    }

    // ✅ STEP 2: Check if we have a valid cached session in sessionStorage
    try {
      const cachedSessionId = sessionStorage.getItem("unified_session_id");
      const cachedExpiry = sessionStorage.getItem("unified_session_expires_at");

      if (
        cachedSessionId &&
        cachedExpiry &&
        Date.now() < parseInt(cachedExpiry)
      ) {
        console.log(
          "⚡ Apollo: Session loaded from unified sessionStorage:",
          cachedSessionId,
        );
        console.log(
          "📱 Apollo: Using client_id:",
          this.clientId ? this.clientId.substring(0, 16) + "..." : "none",
        );

        this.currentSessionId = cachedSessionId;
        this.sessionExpiresAt = parseInt(cachedExpiry);
        return cachedSessionId;
      }
    } catch (error) {
      console.warn("Apollo: Failed to read from session storage:", error);
    }

    // ✅ STEP 3: Check if we have a valid session in memory
    if (
      this.currentSessionId &&
      this.sessionExpiresAt &&
      Date.now() < this.sessionExpiresAt
    ) {
      return this.currentSessionId;
    }

    // ✅ STEP 4: No cached session, create new one
    try {
      const url = `${this.baseUrl}/api/apollo/get-or-create-session`;

      const browserSessionId = this.getBrowserSessionId();

      const payload: UnifiedSessionRequest = {
        shop_id: shopId,
        customer_id: customerId || undefined,
        browser_session_id: browserSessionId,
        client_id: this.clientId || undefined, // ✅ Include client_id if available
        user_agent: navigator.userAgent,
        ip_address: undefined,
        referrer: document.referrer,
        page_url: window.location.href,
      };

      console.log("🌐 Apollo: Creating session with:", {
        shop_id: shopId,
        has_customer: !!customerId,
        has_client_id: !!this.clientId,
        browser_session_id: browserSessionId,
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
        this.currentSessionId = sessionId;
        this.sessionExpiresAt = Date.now() + 30 * 60 * 1000;

        // ✅ NEW: Store client_id from backend response
        if (result.data.client_id && !this.clientId) {
          this.clientId = result.data.client_id;
          this.storeClientId(this.clientId);
        }

        // Store session in sessionStorage (shared across all extensions)
        try {
          sessionStorage.setItem("unified_session_id", sessionId);
          sessionStorage.setItem(
            "unified_session_expires_at",
            this.sessionExpiresAt.toString(),
          );
          console.log(
            "💾 Apollo: Session saved to unified sessionStorage:",
            sessionId,
          );
        } catch (error) {
          console.warn("Apollo: Failed to store session:", error);
        }

        console.log("🔄 Apollo: Session created/retrieved:", sessionId);
        return sessionId;
      } else {
        throw new Error(result.message || "Failed to create session");
      }
    } catch (error) {
      console.error("💥 Apollo: Session creation error:", error);
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

  /**
   * Get client_id from sessionStorage (set by Atlas or other extensions)
   * ✅ NEW METHOD
   */
  private getClientIdFromStorage(): string | null {
    try {
      const clientId = sessionStorage.getItem("unified_client_id");
      if (clientId) {
        console.log(
          "📱 Apollo: Found client_id in sessionStorage:",
          clientId.substring(0, 16) + "...",
        );
        return clientId;
      }
    } catch (error) {
      console.warn(
        "Apollo: Failed to read client_id from sessionStorage:",
        error,
      );
    }
    return null;
  }

  /**
   * Store client_id in sessionStorage for other extensions
   * ✅ NEW METHOD
   */
  private storeClientId(clientId: string): void {
    try {
      sessionStorage.setItem("unified_client_id", clientId);
      console.log(
        "📱 Apollo: Stored client_id in sessionStorage:",
        clientId.substring(0, 16) + "...",
      );
    } catch (error) {
      console.warn("Apollo: Failed to store client_id:", error);
    }
  }
}

// Default instance
export const apolloAnalytics = new ApolloAnalyticsClient();
