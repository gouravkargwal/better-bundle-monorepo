class AnalyticsApiClient {
  constructor() {
    this.baseUrl = "https://c5da58a2ed7b.ngrok-free.app"; // Update this to your actual backend URL
    this.currentSessionId = null;
    this.sessionExpiresAt = null;
    this.clientId = null;  // ✅ Store client_id in memory
    this.trackedEvents = new Map();
    this.deduplicationWindow = 5000; // 5 seconds
  }


  async getBrowserSessionId() {
    let sessionId = sessionStorage.getItem("unified_browser_session_id");
    if (!sessionId) {
      sessionId = "unified_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
      sessionStorage.setItem("unified_browser_session_id", sessionId);
      console.log("🆕 Phoenix: Generated new unified browser_session_id:", sessionId);
    } else {
      console.log("♻️ Phoenix: Reusing existing unified browser_session_id:", sessionId);
    }
    return sessionId;
  }

  getClientIdFromStorage() {
    try {
      const clientId = sessionStorage.getItem("unified_client_id");
      if (clientId) {
        console.log("📱 Phoenix: Found client_id in sessionStorage:", clientId.substring(0, 16) + "...");
        return clientId;
      }
    } catch (error) {
      console.warn("Phoenix: Failed to read client_id from sessionStorage:", error);
    }
    return null;
  }

  async getOrCreateSession(shopDomain, customerId) {
    try {
      if (!this.clientId) {
        this.clientId = this.getClientIdFromStorage();
      }

      const cachedSessionId = sessionStorage.getItem("unified_session_id");
      const cachedExpiry = sessionStorage.getItem("unified_session_expires_at");

      if (cachedSessionId && cachedExpiry && Date.now() < parseInt(cachedExpiry)) {
        console.log("⚡ Phoenix: Session loaded from unified sessionStorage:", cachedSessionId);
        console.log("📱 Phoenix: Using client_id:", this.clientId ? this.clientId.substring(0, 16) + "..." : "none");

        this.currentSessionId = cachedSessionId;
        this.sessionExpiresAt = parseInt(cachedExpiry);
        return cachedSessionId;
      }

      if (this.currentSessionId && this.sessionExpiresAt && Date.now() < this.sessionExpiresAt) {
        return this.currentSessionId;
      }

      const url = `${this.baseUrl}/api/phoenix/get-or-create-session`;
      const browserSessionId = await this.getBrowserSessionId();

      const payload = {
        shop_domain: shopDomain,
        customer_id: customerId ? String(customerId) : undefined,
        browser_session_id: browserSessionId,
        client_id: this.clientId,  // ✅ Include client_id if available
        user_agent: navigator.userAgent,
        ip_address: null,
        referrer: document.referrer,
        page_url: window.location.href,
      };

      console.log('🔍 Phoenix: Session request:', {
        url,
        has_client_id: !!this.clientId,
        browser_session_id: browserSessionId
      });

      // Create AbortController for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        keepalive: true,
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        console.error(`❌ Analytics: Session creation failed with status ${response.status}`);
        throw new Error(`Session creation failed: ${response.status}`);
      }

      const result = await response.json();

      if (result.success && result.data && result.data.session_id) {
        const sessionId = result.data.session_id;
        const expiresAt = Date.now() + 30 * 60 * 1000;

        // Store in memory
        this.currentSessionId = sessionId;
        this.sessionExpiresAt = expiresAt;

        // ✅ NEW: Store client_id from backend response
        if (result.data.client_id && !this.clientId) {
          this.clientId = result.data.client_id;
          // Also store in sessionStorage for other extensions
          try {
            sessionStorage.setItem("unified_client_id", this.clientId);
            console.log("📱 Phoenix: Stored client_id from backend:", this.clientId.substring(0, 16) + "...");
          } catch (error) {
            console.warn("Phoenix: Failed to store client_id:", error);
          }
        }

        sessionStorage.setItem("unified_session_id", sessionId);
        sessionStorage.setItem("unified_session_expires_at", expiresAt.toString());
        console.log("💾 Phoenix: Session saved to unified sessionStorage:", sessionId);
        return sessionId;
      } else {
        throw new Error(result.message || "Failed to create session");
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        console.error("⏰ Analytics: Session creation timed out after 5 seconds");
      } else {
        console.error("💥 Phoenix: Session creation error:", error);
      }
      throw error;
    }
  }

  shouldDeduplicateEvent(eventKey) {
    const now = Date.now();
    const lastTracked = this.trackedEvents.get(eventKey);

    if (lastTracked && (now - lastTracked) < this.deduplicationWindow) {
      return true;
    }

    this.trackedEvents.set(eventKey, now);
    return false;
  }


  async trackUnifiedInteraction(request) {
    try {

      const eventKey = `${request.interaction_type}_${request.context}_${request.shop_domain}_${request.customer_id || 'anon'}`;

      if (this.shouldDeduplicateEvent(eventKey)) {
        return true; // Return success but don't actually track
      }

      const sessionId = await this.getOrCreateSession(request.shop_domain, request.customer_id ? String(request.customer_id) : undefined);

      const interactionData = {
        ...request,
        session_id: sessionId,
      };

      const url = `${this.baseUrl}/api/phoenix/track-interaction`;

      console.log('📊 Phoenix track-interaction request:', { url, interactionData });

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(interactionData),
        keepalive: true,
      });

      console.log('📊 Phoenix track-interaction response:', {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok
      });


      if (!response.ok) {
        throw new Error(`Interaction tracking failed: ${response.status}`);
      }

      const result = await response.json();

      if (result.success) {
        return true;
      } else {
        throw new Error(result.message || "Failed to track interaction");
      }
    } catch (error) {
      console.error("💥 Phoenix interaction tracking error:", error);
      return false;
    }
  }



  async trackRecommendationView(shopDomain, context, customerId, productIds, metadata) {
    try {

      const request = {
        session_id: "",
        shop_domain: shopDomain,
        context: context, // Use consistent context (cart)
        interaction_type: "recommendation_viewed",
        customer_id: customerId ? String(customerId) : undefined,
        page_url: window.location.href,
        referrer: document.referrer,
        metadata: {
          ...metadata,
          extension_type: "phoenix",
          source: "phoenix_theme_extension",
          // Standard structure expected by adapters
          data: {
            recommendations: productIds?.map((productId, index) => ({
              id: productId,
              position: index + 1
            })) || [],
            type: "recommendation",
            widget: "phoenix_recommendation",
            algorithm: "phoenix_algorithm"
          }
        },
      };

      const result = await this.trackUnifiedInteraction(request);
      return result;
    } catch (error) {
      console.error("Failed to track recommendation view:", error);
      return false;
    }
  }

  /**
   * Track recommendation click (when user clicks on a recommendation)
   */
  async trackRecommendationClick(shopDomain, context, productId, position, customerId, metadata) {
    try {
      const request = {
        session_id: "", // Will be set by trackUnifiedInteraction
        shop_domain: shopDomain,
        context: context,
        interaction_type: "recommendation_clicked", // Use custom recommendation event
        customer_id: customerId ? String(customerId) : undefined,
        product_id: productId,
        page_url: window.location.href,
        referrer: document.referrer,
        metadata: {
          ...metadata,
          extension_type: "phoenix",
          source: "phoenix_theme_extension",
          // Standard structure expected by adapters
          data: {
            product: {
              id: productId
            },
            type: "recommendation",
            position: position,
            widget: "phoenix_recommendation",
            algorithm: "phoenix_algorithm"
          }
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
  async trackAddToCart(shopDomain, context, productId, variantId, position, customerId, metadata) {
    try {
      const request = {
        session_id: "", // Will be set by trackUnifiedInteraction
        shop_domain: shopDomain,
        context: context,
        interaction_type: "recommendation_add_to_cart", // Use custom recommendation event
        customer_id: customerId ? String(customerId) : undefined,
        product_id: productId,
        page_url: window.location.href,
        referrer: document.referrer,
        metadata: {
          ...metadata,
          extension_type: "phoenix",
          source: "phoenix_theme_extension",
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
            widget: "phoenix_recommendation",
            algorithm: "phoenix_algorithm"
          }
        },
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      console.error("Failed to track add to cart:", error);
      return false;
    }
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