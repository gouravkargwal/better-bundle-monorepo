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
    [key: string]: any;
  };
}

class AnalyticsApiClient {
  private baseUrl: string;
  private currentSessionId: string | null = null;
  private sessionExpiresAt: number | null = null;

  constructor() {
    // Use the unified analytics service URL
    this.baseUrl = "https://d242bda5e5c7.ngrok-free.app";
  }

  /**
   * Get or create a session for Venus tracking
   */
  async getOrCreateSession(
    shopDomain: string,
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
      const url = `${this.baseUrl}/api/venus/get-or-create-session`;

      const payload: UnifiedSessionRequest = {
        shop_domain: shopDomain,
        customer_id: customerId || null,
        browser_session_id: null,
        user_agent: navigator.userAgent,
        ip_address: null, // Will be detected server-side
        referrer: null,
        page_url: null,
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

      if (result.success && result.data) {
        this.currentSessionId = result.data.session_id!;
        // Set session to expire 30 minutes from now (server handles actual expiration)
        this.sessionExpiresAt = Date.now() + 30 * 60 * 1000;

        console.log(
          "🔄 Venus session created/retrieved:",
          this.currentSessionId,
        );
        return this.currentSessionId;
      } else {
        throw new Error(result.message || "Failed to create session");
      }
    } catch (error) {
      console.error("💥 Venus session creation error:", error);
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

  /**
   * Track extension activity (load events)
   * Note: No localStorage throttling in extensions - backend handles throttling
   */
  async trackExtensionLoad(
    shopDomainOrCustomerId: string,
    appBlockTarget: string,
    pageUrl: string,
  ): Promise<boolean> {
    const extensionUid = "883039ef-d1b1-d011-d986-bea48c7c43777e121c7c";

    console.log(`[Venus Tracker] Tracking extension activity:`, {
      shopDomainOrCustomerId,
      extensionUid,
      appBlockTarget,
      timestamp: new Date().toISOString(),
    });

    // Always call the API - backend handles throttling (1 hour window)
    const success = await this.reportExtensionActivity(
      shopDomainOrCustomerId,
      appBlockTarget,
      extensionUid,
      pageUrl,
    );

    if (success) {
      console.log(`[Venus Tracker] Successfully tracked extension activity`);
    } else {
      console.warn(`[Venus Tracker] Failed to track extension activity`);
    }

    return success;
  }

  /**
   * Report extension activity to the API
   * Handles both shop domain and customer ID scenarios
   */
  private async reportExtensionActivity(
    shopDomainOrCustomerId: string,
    appBlockTarget: string,
    extensionUid: string,
    pageUrl: string,
  ): Promise<boolean> {
    try {
      // Determine if we have a shop domain (contains .myshopify.com) or customer ID
      const isShopDomain =
        shopDomainOrCustomerId.includes(".myshopify.com") ||
        shopDomainOrCustomerId.includes(".myshopify.com");

      const requestBody = {
        extension_type: "venus",
        extension_uid: extensionUid,
        page_url: pageUrl,
        app_block_target: appBlockTarget,
        app_block_location: this.getAppBlockLocation(appBlockTarget),
        // Include both shop_domain and customer_id, backend will use what's available
        shop_domain: isShopDomain ? shopDomainOrCustomerId : null,
        customer_id: !isShopDomain ? shopDomainOrCustomerId : null,
      };

      // Use a generic endpoint that can handle both scenarios
      const endpoint = `${this.baseUrl}/extension-activity/track-load`;

      console.log(`[Venus Tracker] Sending API request:`, {
        url: endpoint,
        requestBody,
        timestamp: new Date().toISOString(),
        isShopDomain,
      });

      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      console.log(`[Venus Tracker] API response:`, {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`[Venus Tracker] API error response:`, errorText);
        throw new Error(
          `HTTP error! status: ${response.status}, body: ${errorText}`,
        );
      }

      const responseData = await response.json();
      console.log(
        `[Venus Tracker] Successfully tracked activity:`,
        responseData,
      );

      return true;
    } catch (error) {
      console.error(`[Venus Tracker] Failed to track activity:`, {
        error: error.message,
        stack: error.stack,
        shopDomainOrCustomerId,
        extensionUid,
        appBlockTarget,
        pageUrl,
      });
      return false;
    }
  }

  /**
   * Get app block location description
   */
  private getAppBlockLocation(appBlockTarget: string): string {
    const locationMap = {
      customer_account_order_status_block_render: "Order Status Page",
      customer_account_order_index_block_render: "Order History Page",
      customer_account_profile_block_render: "Profile Page",
      checkout_post_purchase: "Checkout Page",
      theme_app_extension: "Theme Extension",
      web_pixel_extension: "Web Pixel",
    };

    return locationMap[appBlockTarget] || "Unknown Location";
  }
}

// Default instance
export const analyticsApi = new AnalyticsApiClient();
