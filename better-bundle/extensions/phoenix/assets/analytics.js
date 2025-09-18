/**
 * Unified Analytics API Client for BetterBundle Phoenix Extension
 * 
 * This client handles all analytics and attribution tracking using the unified analytics system.
 * Designed specifically for Shopify Theme Extensions with their unique constraints.
 */

class AnalyticsApiClient {
  constructor() {
    // Use the unified analytics service URL
    // For production, this should be your actual backend URL
    // For development, you can use ngrok or localhost
    this.baseUrl = "https://d242bda5e5c7.ngrok-free.app"; // Update this to your actual backend URL
    this.currentSessionId = null;
    this.sessionExpiresAt = null;

    // Deduplication tracking to prevent duplicate events
    this.trackedEvents = new Map();
    this.deduplicationWindow = 5000; // 5 seconds
  }

  /**
   * Get or create a session for Phoenix tracking - OPTIMIZED WITH SESSION STORAGE
   */
  async getOrCreateSession(shopId, customerId) {
    const sessionKey = `unified_session_${shopId}_${customerId || 'anon'}`;
    const expiryKey = `unified_session_expiry_${shopId}_${customerId || 'anon'}`;

    // OPTIMIZATION: Check session storage first (fastest)
    try {
      const cachedSessionId = sessionStorage.getItem(sessionKey);
      const cachedExpiry = sessionStorage.getItem(expiryKey);

      if (cachedSessionId && cachedExpiry && Date.now() < parseInt(cachedExpiry)) {
        console.log("⚡ Phoenix session loaded from cache:", cachedSessionId);
        this.currentSessionId = cachedSessionId;
        this.sessionExpiresAt = parseInt(cachedExpiry);
        return cachedSessionId;
      }
    } catch (error) {
      console.warn("Failed to read from session storage:", error);
    }

    // OPTIMIZATION: Check in-memory cache second
    if (this.currentSessionId && this.sessionExpiresAt && Date.now() < this.sessionExpiresAt) {
      console.log("⚡ Phoenix session loaded from memory:", this.currentSessionId);
      return this.currentSessionId;
    }

    // OPTIMIZATION: Only make API call if no valid cached session
    try {
      const url = `${this.baseUrl}/api/phoenix/get-or-create-session`;

      const payload = {
        shop_id: shopId,
        customer_id: customerId ? String(customerId) : undefined,
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
        const expiresAt = Date.now() + 30 * 60 * 1000; // 30 minutes

        // OPTIMIZATION: Store in both memory and session storage
        this.currentSessionId = sessionId;
        this.sessionExpiresAt = expiresAt;

        try {
          sessionStorage.setItem(sessionKey, sessionId);
          sessionStorage.setItem(expiryKey, expiresAt.toString());
        } catch (error) {
          console.warn("Failed to store session in session storage:", error);
        }

        console.log("🔄 Phoenix session created/retrieved from API:", sessionId);
        return sessionId;
      } else {
        throw new Error(result.message || "Failed to create session");
      }
    } catch (error) {
      console.error("💥 Phoenix session creation error:", error);

      // OPTIMIZATION: Fallback to browser session ID if API fails
      const fallbackSessionId = this.getBrowserSessionId();
      console.log("🔄 Using fallback session ID:", fallbackSessionId);
      return fallbackSessionId;
    }
  }

  /**
   * Check if an event should be deduplicated
   */
  shouldDeduplicateEvent(eventKey) {
    const now = Date.now();
    const lastTracked = this.trackedEvents.get(eventKey);

    if (lastTracked && (now - lastTracked) < this.deduplicationWindow) {
      console.log(`🔄 Deduplicating event: ${eventKey} (tracked ${now - lastTracked}ms ago)`);
      return true;
    }

    this.trackedEvents.set(eventKey, now);
    return false;
  }

  /**
   * Track interaction using unified analytics
   */
  async trackUnifiedInteraction(request) {
    try {
      // Create deduplication key
      const eventKey = `${request.interaction_type}_${request.context}_${request.shop_id}_${request.customer_id || 'anon'}`;

      // Check for deduplication
      if (this.shouldDeduplicateEvent(eventKey)) {
        return true; // Return success but don't actually track
      }

      // Get or create session first
      const sessionId = await this.getOrCreateSession(request.shop_id, request.customer_id ? String(request.customer_id) : undefined);

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
        context: context, // Use consistent context (cart)
        interaction_type: "recommendation_viewed",
        customer_id: customerId ? String(customerId) : undefined,
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
        interaction_type: "recommendation_clicked", // Use custom recommendation event
        customer_id: customerId ? String(customerId) : undefined,
        product_id: productId,
        page_url: window.location.href,
        referrer: document.referrer,
        metadata: {
          ...metadata,
          extension_type: "phoenix",
          recommendation_position: position,
          source: "phoenix_theme_extension",
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
        interaction_type: "recommendation_add_to_cart", // Use custom recommendation event
        customer_id: customerId ? String(customerId) : undefined,
        product_id: productId,
        page_url: window.location.href,
        referrer: document.referrer,
        metadata: {
          ...metadata,
          extension_type: "phoenix",
          variant_id: variantId,
          recommendation_position: position,
          source: "phoenix_theme_extension",
        },
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      console.error("Failed to track add to cart:", error);
      return false;
    }
  }

  /**
   * Get unified browser session ID (shared across all extensions)
   */
  getBrowserSessionId() {
    // Use unified session ID that all extensions share
    let sessionId = sessionStorage.getItem("unified_browser_session_id");
    if (!sessionId) {
      sessionId = "unified_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
      sessionStorage.setItem("unified_browser_session_id", sessionId);
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