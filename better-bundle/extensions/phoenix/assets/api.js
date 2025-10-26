class RecommendationAPI {
  constructor() {
    // Use config for base URL
    this.baseUrl = window.getBaseUrl ? window.getBaseUrl() : "https://nonconscientious-annette-saddeningly.ngrok-free.dev";
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
      const context = window.context || 'homepage';
      const shopDomain = window.shopDomain || '';
      this.logger.info('API: Fetching recommendations for shop domain:', shopDomain);
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

      // Add context-specific fields
      if (context === 'product_page' && window.productId) {
        requestBody.product_id = String(window.productId);
      }
      if (context === 'product_page_similar' && window.productId) {
        requestBody.product_id = String(window.productId);
      }
      if (context === 'product_page_frequently_bought' && window.productId) {
        requestBody.product_id = String(window.productId);
      }
      if (context === 'product_page_customers_viewed' && window.productId) {
        requestBody.product_id = String(window.productId);
      }
      if (context === 'collection_page' && window.collectionId) {
        requestBody.collection_id = String(window.collectionId);
      }

      // Add homepage-specific visitor strategy
      if (context === 'homepage' && window.visitorStrategy) {
        requestBody.metadata = requestBody.metadata || {};
        requestBody.metadata.visitor_strategy = window.visitorStrategy;
      }

      // Add optional fields if available
      if (productIds) requestBody.product_ids = productIds.map(id => String(id)); // Convert all product IDs to strings
      if (customerId) requestBody.user_id = String(customerId); // Convert to string as backend expects string

      // Get session_id from sessionStorage (unified across all extensions)
      const unifiedSessionId = sessionStorage.getItem('unified_session_id');
      if (unifiedSessionId) {
        requestBody.session_id = unifiedSessionId;
      } else if (window.sessionId) {
        requestBody.session_id = String(window.sessionId); // Fallback to window.sessionId
      }

      const apiUrl = `${this.baseUrl}/api/v1/recommendations`;

      // Create AbortController for timeout with retry logic
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

      // Use JWT authentication for the request
      const response = await this.phoenixJWT.makeAuthenticatedRequest(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
        signal: controller.signal,
        keepalive: true // Keep connection alive for better performance
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
        this.logger.error('⏰ API: Request timed out after 10 seconds');
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
        throw new Error(`Cart API error: ${response.status}`);
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
