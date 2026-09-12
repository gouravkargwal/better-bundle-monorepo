class RecommendationAPI {
  constructor() {
    // Use config for base URL
    this.baseUrl = window.getBaseUrl();
    this.logger = window.phoenixLogger || console; // Use the global logger with fallback
    this.phoenixJWT = null; // Will be set by PhoenixJWT manager
    this.isLoading = false; // Prevent duplicate API calls
  }

  /**
   * Set Phoenix JWT manager reference
   */
  setPhoenixJWT(phoenixJWT) {
    this.phoenixJWT = phoenixJWT;
  }

  async fetchRecommendations(productIds, customerId, limit = 4) {
    try {
      const context = window.context || 'product_page';
      const shopDomain = window.shopDomain || '';
      if (!shopDomain) {
        this.logger.error('❌ API: Shop domain is required but not provided');
        throw new Error('Shop domain is required but not provided');
      }

      // Check if Phoenix JWT is available and initialized
      if (!this.phoenixJWT || !this.phoenixJWT.isReady()) {
        this.logger.error('❌ API: Phoenix JWT not initialized');
        throw new Error('Phoenix JWT not initialized');
      }

      // Prevent duplicate API calls
      if (this.isLoading) {
        this.logger.warn('⚠️ API: Request already in progress, skipping');
        return [];
      }
      this.isLoading = true;

      // Build request body for unified recommendation API
      const requestBody = {
        shop_domain: shopDomain,
        context: context,
        limit: limit
      };

      // Not a real shopper: a theme preview link, or the customiser if we ever
      // reach here from it. Recommendations are still served so the merchant
      // can see the widget work, but the backend writes no impression — an
      // offer nobody was shown must not sit in the denominator of the
      // conversion rate they are billed against.
      //
      // design_mode already short-circuits before any fetch; this covers
      // visual_preview_mode, the shareable preview link, where design_mode is
      // false and the page is otherwise indistinguishable from a live visit.
      if (window.previewMode) {
        requestBody.preview = true;
      }

      // The product being viewed is the whole query key: edges are looked up
      // from it. Without it there is nothing to recommend against.
      if (window.productId) {
        requestBody.product_id = String(window.productId);
      }

      // Add optional fields if available
      if (productIds) requestBody.product_ids = productIds.map(id => String(id)); // Convert all product IDs to strings
      if (customerId) requestBody.user_id = String(customerId); // Convert to string as backend expects string

      // Consent-gated visitor id, used only to keep this shopper in a stable
      // holdout bucket. Null when the shopper has not accepted measurement
      // processing, in which case nothing is sent and the backend serves
      // recommendations without bucketing them into the experiment.
      const visitorId = window.bbGetVisitorId ? window.bbGetVisitorId() : null;
      if (visitorId) {
        requestBody.session_id = visitorId;
      }

      // Diagnostics for the theme sniffer, riding a request we were making
      // anyway. No extra round trip, nothing on the critical path, and no
      // shopper data: it is which of our own selectors matched, plus the theme
      // name Shopify itself publishes. It answers the only question we cannot
      // answer from here — which real themes our probe lists fail on.
      if (window.bbThemeAdapt) {
        requestBody.theme_adapt = window.bbThemeAdapt;
      }

      const apiUrl = `${this.baseUrl}/api/v1/recommendations`;

      // Create AbortController for timeout with retry logic
      const controller = new AbortController();
      // 3s, not 10s: the server answers this in ~130ms, so three seconds is
      // already 20x headroom over a slow mobile connection. Ten seconds only
      // ever meant ten seconds of skeleton for a shopper who was never going
      // to see a recommendation.
      const timeoutId = setTimeout(() => controller.abort(), 3000);

      // Use JWT authentication for the request
      // Pass customerId for customer-specific token generation
      const response = await this.phoenixJWT.makeAuthenticatedRequest(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
        signal: controller.signal,
        // No `keepalive`. It was added here as "keep the connection alive for
        // better performance", but that is not what the flag does — it marks a
        // request as allowed to outlive the page, for unload beacons (see
        // attribution.js, where it is correct). Chrome services keepalive
        // requests on a separate low-priority, quota-limited path, which is why
        // this call took seconds in the browser while the server answered in
        // ~130ms.
        customerId: customerId || null, // Pass customerId for token context
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        if (response.status === 403) {
          this.logger.warn('⏸️ API: Services suspended - shop is not active');
          return [];
        }
        this.logger.error(`❌ API: Request failed with status ${response.status}`);
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();

      if (data.success && data.recommendations && data.recommendations.length > 0) {
        return data.recommendations;
      } else {
        return [];
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        this.logger.error('⏰ API: Request timed out after 3 seconds');
      } else {
        this.logger.error('❌ API: Error fetching recommendations from unified API:', error);
      }
      return [];
    } finally {
      this.isLoading = false;
    }
  }

  // Add product to cart using Shopify's native Cart AJAX API
  // Supports passing line item properties for per-item attribution
  async addToCart(variantId, quantity = 1, properties = {}) {
    try {
      // Validate inputs
      if (!variantId) {
        throw new Error('Variant ID is required');
      }
      if (!quantity || quantity < 1) {
        throw new Error('Valid quantity is required');
      }

      const cartPayload = {
        items: [
          {
            id: variantId,
            quantity: quantity,
            // Attach attribution as line item properties (Shopify expects Hash format)
            ...(properties && Object.keys(properties).length > 0
              ? { properties }
              : {})
          }
        ]
      };


      const response = await fetch('/cart/add.js', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cartPayload)
      });

      if (!response.ok) {
        // Parse error response for better error handling
        let errorMessage = `Cart API error: ${response.status}`;
        let errorData = null;

        try {
          errorData = await response.json();
          if (errorData && errorData.description) {
            errorMessage = errorData.description;
          }
        } catch (e) {
          // If response isn't JSON, use status text
          errorMessage = response.statusText || errorMessage;
        }

        // Create error object with status code for proper handling
        const error = new Error(errorMessage);
        error.status = response.status;
        error.statusCode = response.status;
        error.data = errorData;
        throw error;
      }

      const data = await response.json();

      // Dispatch custom event for theme compatibility
      window.dispatchEvent(new CustomEvent('cart:updated', { detail: data }));

      return data;
    } catch (error) {
      this.logger.error('Error adding to cart:', error);
      throw error;
    }
  }
}

// Export for use in other files
window.RecommendationAPI = RecommendationAPI;
