class AnalyticsApiClient {
  constructor() {
    // Use config for base URL
    this.baseUrl = window.getBaseUrl ? window.getBaseUrl() : "https://nonconscientious-annette-saddeningly.ngrok-free.dev";
    this.currentSessionId = null;
    this.sessionExpiresAt = null;
    this.clientId = null; // ✅ Store client_id in memory
    this.trackedEvents = new Map();
    this.deduplicationWindow = 5000; // 5 seconds
    this.logger = window.phoenixLogger || console; // Use the global logger with fallback
    this.phoenixJWT = null; // Will be set by PhoenixJWT manager
  }

  /**
   * Set Phoenix JWT manager reference
   */
  setPhoenixJWT(phoenixJWT) {
    this.phoenixJWT = phoenixJWT;
  }

  async getBrowserSessionId() {
    let sessionId = sessionStorage.getItem("unified_browser_session_id");
    if (!sessionId) {
      sessionId =
        "unified_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
      sessionStorage.setItem("unified_browser_session_id", sessionId);
    }
    return sessionId;
  }

  getClientIdFromStorage() {
    try {
      const clientId = sessionStorage.getItem("unified_client_id");
      if (clientId) {
        return clientId;
      }
    } catch (error) {
      this.logger.error(
        "Phoenix: Failed to read client_id from sessionStorage:",
        error,
      );
    }
    return null;
  }

  async getOrCreateSession(shopDomain, customerId) {
    try {
      // Check if Phoenix JWT is available and initialized
      if (!this.phoenixJWT || !this.phoenixJWT.isReady()) {
        return null;
      }

      // Always try to get client_id from storage first
      if (!this.clientId) {
        this.clientId = this.getClientIdFromStorage();
      }

      const cachedSessionId = sessionStorage.getItem("unified_session_id");
      const cachedExpiry = sessionStorage.getItem("unified_session_expires_at");

      if (
        cachedSessionId &&
        cachedExpiry &&
        Date.now() < parseInt(cachedExpiry)
      ) {
        this.currentSessionId = cachedSessionId;
        this.sessionExpiresAt = parseInt(cachedExpiry);
        return cachedSessionId;
      }

      if (
        this.currentSessionId &&
        this.sessionExpiresAt &&
        Date.now() < this.sessionExpiresAt
      ) {
        return this.currentSessionId;
      }

      const url = `${this.baseUrl}/api/session/get-or-create-session`;
      const browserSessionId = await this.getBrowserSessionId();

      // Get browser_session_id from localStorage if available (backend-generated)
      const storedBrowserSessionId = localStorage.getItem("unified_browser_session_id") || browserSessionId || undefined;

      const payload = {
        shop_domain: shopDomain,
        customer_id: customerId ? String(customerId) : undefined,
        browser_session_id: storedBrowserSessionId || undefined, // Backend will generate if not provided
        client_id: this.clientId || undefined,
        user_agent: true, // Backend will extract from request
        ip_address: true, // Backend will extract from request
        referrer: document.referrer || undefined,
        page_url: window.location.href || undefined,
        extension_type: "phoenix", // ✅ Add this required field
      };

      // Create AbortController for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 8000); // 8 second timeout

      // Use JWT authentication for the request
      // Pass customerId for customer-specific token generation
      const response = await this.phoenixJWT.makeAuthenticatedRequest(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        keepalive: true,
        signal: controller.signal,
        customerId: customerId || null, // Pass customerId for token context
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        if (response.status === 403) {
          return null;
        }
        return null;
      }

      const result = await response.json();

      if (result.success && result.data && result.data.session_id) {
        const sessionId = result.data.session_id;
        const expiresAt = Date.now() + 30 * 60 * 1000;

        // Store in memory
        this.currentSessionId = sessionId;
        this.sessionExpiresAt = expiresAt;

        // ✅ Store client_id from backend response (always update if provided)
        if (result.data.client_id) {
          this.clientId = result.data.client_id;
          // Store in sessionStorage for other extensions
          try {
            sessionStorage.setItem("unified_client_id", this.clientId);
          } catch (error) {
            this.logger.error("Phoenix: Failed to store client_id:", error);
          }
        }

        // ✅ Store backend-generated browser_session_id in localStorage
        if (result.data.browser_session_id) {
          try {
            localStorage.setItem("unified_browser_session_id", result.data.browser_session_id);
          } catch (error) {
            this.logger.error("Phoenix: Failed to store browser_session_id:", error);
          }
        }

        sessionStorage.setItem("unified_session_id", sessionId);
        sessionStorage.setItem(
          "unified_session_expires_at",
          expiresAt.toString(),
        );
        return sessionId;
      } else {
        return null;
      }
    } catch (error) {
      this.logger.error("Phoenix: Failed to get or create session:", error);
      return null;
    }
  }

  shouldDeduplicateEvent(eventKey) {
    const now = Date.now();
    const lastTracked = this.trackedEvents.get(eventKey);

    if (lastTracked && now - lastTracked < this.deduplicationWindow) {
      return true;
    }

    this.trackedEvents.set(eventKey, now);
    return false;
  }

  async trackUnifiedInteraction(request) {
    try {
      // Check if Phoenix JWT is available and initialized
      if (!this.phoenixJWT || !this.phoenixJWT.isReady()) {
        return false;
      }

      const eventKey = `${request.interaction_type}_${request.context}_${request.shop_domain}_${request.customer_id || "anon"}`;

      if (this.shouldDeduplicateEvent(eventKey)) {
        return true; // Return success but don't actually track
      }

      const sessionId = await this.getOrCreateSession(
        request.shop_domain,
        request.customer_id ? String(request.customer_id) : undefined,
      );

      // Build unified interaction payload matching other extensions
      const interactionData = {
        session_id: sessionId,
        shop_domain: request.shop_domain,
        extension_type: "phoenix", // ✅ Required field at top level (not in metadata)
        customer_id: request.customer_id ? String(request.customer_id) : undefined,
        interaction_type: request.interaction_type,
        metadata: {
          // Exclude extension_type from metadata since it's now at top level
          ...request.metadata,
        },
      };

      // Use unified interaction endpoint
      const url = `${this.baseUrl}/api/interaction/track`;

      // Use JWT authentication for the request
      // Pass customerId for customer-specific token generation
      const response = await this.phoenixJWT.makeAuthenticatedRequest(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(interactionData),
        keepalive: true,
        customerId: request.customer_id || null, // Pass customerId for token context
      });

      if (!response.ok) {
        if (response.status === 403) {
          return false;
        }
        return false;
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
      this.logger.error("💥 Phoenix interaction tracking error:", error);
      return false;
    }
  }

  async trackRecommendationView(
    shopDomain,
    context,
    customerId,
    productIds,
    metadata,
  ) {
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
          source: "phoenix_theme_extension",
          // Standard structure expected by adapters
          data: {
            recommendations:
              productIds?.map((productId, index) => ({
                id: productId,
                position: index + 1,
              })) || [],
            type: "recommendation",
            widget: "phoenix_recommendation",
            algorithm: "phoenix_algorithm",
          },
        },
      };

      const result = await this.trackUnifiedInteraction(request);
      return result;
    } catch (error) {
      this.logger.error("Phoenix: Failed to track recommendation view:", error);
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
    customerId,
    metadata,
  ) {
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
          source: "phoenix_theme_extension",
          // Standard structure expected by adapters
          data: {
            product: {
              id: productId,
            },
            type: "recommendation",
            position: position,
            widget: "phoenix_recommendation",
            algorithm: "phoenix_algorithm",
          },
        },
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      this.logger.error("Phoenix: Failed to track recommendation click:", error);
      return false;
    }
  }

  /**
   * Track add to cart action
   */
  async trackAddToCart(
    shopDomain,
    context,
    productId,
    variantId,
    position,
    customerId,
    metadata,
  ) {
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
          source: "phoenix_theme_extension",
          // Standard structure expected by adapters
          data: {
            cartLine: {
              merchandise: {
                id: variantId,
                product: {
                  id: productId, // Use productId instead of variantId for product_id
                },
              },
              quantity: metadata?.quantity || 1,
            },
            type: "recommendation",
            position: position,
            widget: "phoenix_recommendation",
            algorithm: "phoenix_algorithm",
            // ✅ Add quantity tracking for proper attribution
            selected_quantity: metadata?.quantity || 1,
          },
        },
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      this.logger.error("Phoenix: Failed to track add to cart:", error);
      return false;
    }
  }

  /**
   * Store attribution data in cart attributes for order processing
   */
  async storeCartAttribution(
    sessionId,
    productId,
    context,
    position,
    quantity = 1,
  ) {
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
            bb_recommendation_quantity: quantity.toString(), // ✅ Add quantity to cart attributes
            bb_recommendation_timestamp: new Date().toISOString(),
            bb_recommendation_source: "betterbundle",
          },
        }),
      });

      return response.ok;
    } catch (error) {
      this.logger.error("Phoenix: Failed to store cart attribution:", error);
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
