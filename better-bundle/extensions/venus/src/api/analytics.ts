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
    client_id?: string; // ✅ NEW
    [key: string]: any;
  };
}

class AnalyticsApiClient {
  private baseUrl: string;
  private currentSessionId: string | null = null;
  private sessionExpiresAt: number | null = null;
  private clientId: string | null = null;
  private customerId: string | null = null;
  constructor() {
    // Use the unified analytics service URL
    this.baseUrl = "https://c5da58a2ed7b.ngrok-free.app";
  }

  async getOrCreateSession(
    shopDomain: string,
    customerId: string, // ✅ Venus ALWAYS has customer_id (logged in context)
  ): Promise<string> {
    // ✅ STEP 1: Check if we have a valid session in memory
    // This avoids multiple API calls within the same page session
    if (
      this.currentSessionId &&
      this.sessionExpiresAt &&
      Date.now() < this.sessionExpiresAt &&
      this.customerId === customerId // Ensure same customer
    ) {
      console.log(
        "⚡ Venus: Using cached session from memory:",
        this.currentSessionId,
      );
      console.log(
        "📱 Venus: client_id:",
        this.clientId ? this.clientId.substring(0, 16) + "..." : "none",
      );
      return this.currentSessionId;
    }

    // ✅ STEP 2: No valid cached session, call backend
    try {
      const url = `${this.baseUrl}/api/venus/get-or-create-session`;

      const payload: UnifiedSessionRequest = {
        shop_domain: shopDomain,
        customer_id: customerId, // Primary identifier for Venus
        browser_session_id: null, // Venus doesn't have access to this
        client_id: null, // Backend will return if available from other extensions
        user_agent: navigator.userAgent,
        ip_address: undefined,
        referrer: undefined,
        page_url: window.location.href,
      };

      console.log("🌐 Venus: Creating session with:", {
        shop_domain: shopDomain,
        customer_id: customerId.substring(0, 20) + "...",
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

        // Store in memory (valid for component lifetime only)
        this.currentSessionId = sessionId;
        this.customerId = customerId;
        this.sessionExpiresAt = Date.now() + 30 * 60 * 1000; // 30 min cache

        // ✅ Store client_id from backend if available
        if (result.data.client_id) {
          this.clientId = result.data.client_id;
          console.log(
            "📱 Venus: Received client_id from backend:",
            this.clientId.substring(0, 16) + "...",
          );
        }

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
      // Get or create session first
      const sessionId = await this.getOrCreateSession(
        request.shop_domain,
        request.customer_id,
      );

      // Update request with session ID
      const interactionData = {
        ...request,
        session_id: sessionId,
      };

      // Send to unified analytics endpoint
      const url = `${this.baseUrl}/api/venus/track-interaction`;

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

  /**
   * Track recommendation view (when recommendations are displayed)
   */
  async trackRecommendationView(
    shopDomain: string,
    context: ExtensionContext,
    customerId?: string,
    productIds?: string[],
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    try {
      const request: UnifiedInteractionRequest = {
        session_id: "", // Will be set by trackUnifiedInteraction
        shop_domain: shopDomain,
        context,
        interaction_type: "recommendation_viewed",
        customer_id: customerId,
        page_url: null,
        referrer: null,
        metadata: {
          ...metadata,
          extension_type: "venus",
          product_ids: productIds,
          recommendation_count: productIds?.length || 0,
          source: "venus_recommendation",
        },
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
    customerId?: string,
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    try {
      const request: UnifiedInteractionRequest = {
        session_id: "", // Will be set by trackUnifiedInteraction
        shop_domain: shopDomain,
        context,
        interaction_type: "recommendation_clicked",
        customer_id: customerId,
        product_id: productId,
        page_url: null,
        referrer: null,
        metadata: {
          ...metadata,
          extension_type: "venus",
          position,
          source: "venus_recommendation",
          interaction_type: "recommendation_clicked",
        },
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      console.error("Failed to track recommendation click:", error);
      return false;
    }
  }

  /**
   * Track shop now action (when user clicks "Shop Now" button)
   */
  async trackShopNow(
    shopDomain: string,
    context: ExtensionContext,
    productId: string,
    position: number,
    customerId?: string,
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    try {
      const request: UnifiedInteractionRequest = {
        session_id: "", // Will be set by trackUnifiedInteraction
        shop_domain: shopDomain,
        context,
        interaction_type: "recommendation_clicked",
        customer_id: customerId,
        product_id: productId,
        page_url: null,
        referrer: null,
        metadata: {
          ...metadata,
          extension_type: "venus",
          position,
          source: "venus_recommendation",
          interaction_type: "recommendation_clicked",
        },
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      console.error("Failed to track shop now:", error);
      return false;
    }
  }

  /**
   * Store attribution data in cart attributes for order processing
   */
  async storeCartAttribution(
    sessionId: string,
    productId: string,
    context: ExtensionContext,
    position: number,
  ): Promise<boolean> {
    try {
      const response = await fetch("/cart/update.js", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          attributes: {
            bb_recommendation_session_id: sessionId,
            bb_recommendation_product_id: productId,
            bb_recommendation_extension: "venus",
            bb_recommendation_context: context,
            bb_recommendation_position: position.toString(),
            bb_recommendation_timestamp: new Date().toISOString(),
            bb_recommendation_source: "betterbundle",
          },
        }),
      });

      return response.ok;
    } catch (error) {
      console.error("Failed to store cart attribution:", error);
      return false;
    }
  }
}

// Default instance
export const analyticsApi = new AnalyticsApiClient();
