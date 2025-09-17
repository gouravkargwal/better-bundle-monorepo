/**
 * Unified Analytics API Client for BetterBundle Phoenix Extension
 * 
 * This client handles all analytics and attribution tracking using the unified analytics system.
 * Designed specifically for Shopify Theme Extensions with their unique constraints.
 */

class AnalyticsApiClient {
  constructor() {
    // Use the unified analytics service URL
    this.baseUrl = "https://d242bda5e5c7.ngrok-free.app";
    this.currentSessionId = null;
    this.sessionExpiresAt = null;
  }

  /**
   * Get or create a session for Phoenix tracking
   */
  async getOrCreateSession(shopId, customerId) {
    // Check if we have a valid session
    if (this.currentSessionId && this.sessionExpiresAt && Date.now() < this.sessionExpiresAt) {
      return this.currentSessionId;
    }

    try {
      const url = `${this.baseUrl}/api/phoenix/get-or-create-session`;

      const payload = {
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

      const result = await response.json();

      if (result.success && result.data && result.data.session_id) {
        const sessionId = result.data.session_id;
        this.currentSessionId = sessionId;
        // Set session to expire 30 minutes from now (server handles actual expiration)
        this.sessionExpiresAt = Date.now() + 30 * 60 * 1000;

        console.log("🔄 Phoenix session created/retrieved:", sessionId);
        return sessionId;
      } else {
        throw new Error(result.message || "Failed to create session");
      }
    } catch (error) {
      console.error("💥 Phoenix session creation error:", error);
      throw error;
    }
  }

  /**
   * Track interaction using unified analytics
   */
  async trackUnifiedInteraction(request) {
    try {
      // Get or create session first
      const sessionId = await this.getOrCreateSession(request.shop_id, request.customer_id);

      // Update request with session ID
      const interactionData = {
        ...request,
        session_id: sessionId,
      };

      // Send to unified analytics endpoint
      const url = `${this.baseUrl}/api/phoenix/track-interaction`;

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

      const result = await response.json();

      if (result.success) {
        console.log("✅ Phoenix interaction tracked:", result.data?.interaction_id);
        return true;
      } else {
        throw new Error(result.message || "Failed to track interaction");
      }
    } catch (error) {
      console.error("💥 Phoenix interaction tracking error:", error);
      return false;
    }
  }

  /**
   * Track recommendation view (when recommendations are displayed)
   */
  async trackRecommendationView(shopId, context, customerId, productIds, metadata) {
    try {
      const request = {
        session_id: "", // Will be set by trackUnifiedInteraction
        shop_id: shopId,
        context: context,
        interaction_type: "view",
        customer_id: customerId,
        page_url: window.location.href,
        referrer: document.referrer,
        metadata: {
          ...metadata,
          extension_type: "phoenix",
          product_ids: productIds,
          recommendation_count: productIds?.length || 0,
          source: "phoenix_theme_extension",
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
  async trackRecommendationClick(shopId, context, productId, position, customerId, metadata) {
    try {
      const request = {
        session_id: "", // Will be set by trackUnifiedInteraction
        shop_id: shopId,
        context: context,
        interaction_type: "click",
        customer_id: customerId,
        product_id: productId,
        page_url: window.location.href,
        referrer: document.referrer,
        metadata: {
          ...metadata,
          extension_type: "phoenix",
          position,
          source: "phoenix_theme_extension",
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
   * Track add to cart action
   */
  async trackAddToCart(shopId, context, productId, variantId, position, customerId, metadata) {
    try {
      const request = {
        session_id: "", // Will be set by trackUnifiedInteraction
        shop_id: shopId,
        context: context,
        interaction_type: "add_to_cart",
        customer_id: customerId,
        product_id: productId,
        page_url: window.location.href,
        referrer: document.referrer,
        metadata: {
          ...metadata,
          extension_type: "phoenix",
          variant_id: variantId,
          position,
          source: "phoenix_theme_extension",
          interaction_type: "add_to_cart",
        },
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      console.error("Failed to track add to cart:", error);
      return false;
    }
  }

  /**
   * Get browser session ID (fallback if no session exists)
   */
  getBrowserSessionId() {
    let sessionId = sessionStorage.getItem("phoenix_session_id");
    if (!sessionId) {
      sessionId = "phoenix_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
      sessionStorage.setItem("phoenix_session_id", sessionId);
    }
    return sessionId;
  }


  /**
   * Store attribution data in cart attributes for order processing
   */
  async storeCartAttribution(sessionId, productId, context, position) {
    try {
      const response = await fetch("/cart/update.js", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          attributes: {
            bb_recommendation_session_id: sessionId,
            bb_recommendation_product_id: productId,
            bb_recommendation_extension: "phoenix",
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
   * Generate a short reference ID for attribution URLs
   */
  generateShortRef(sessionId) {
    return sessionId
      .split("")
      .reduce((hash, char) => {
        return ((hash << 5) - hash + char.charCodeAt(0)) & 0xffffffff;
      }, 0)
      .toString(36)
      .substring(0, 6);
  }

  /**
   * Add attribution parameters to product URL
   */
  addAttributionToUrl(productUrl, productId, position, sessionId) {
    const shortRef = this.generateShortRef(sessionId);
    const attributionParams = new URLSearchParams({
      ref: shortRef,
      src: productId,
      pos: position.toString(),
    });

    return `${productUrl}?${attributionParams.toString()}`;
  }
}

// Create global instance
window.analyticsApi = new AnalyticsApiClient();