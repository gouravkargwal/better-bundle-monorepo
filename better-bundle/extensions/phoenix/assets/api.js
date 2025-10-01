
class RecommendationAPI {
  constructor() {
    this.baseUrl = "https://c5da58a2ed7b.ngrok-free.app"; // Update this to your actual backend URL
    this.shopifyBaseUrl = window.location.origin; // For Shopify API calls
  }



  async fetchRecommendations(productIds, customerId, limit = 4) {
    try {
      const context = 'cart';
      const shopDomain = window.shopDomain || '';
      // Validate required fields
      if (!shopDomain) {
        throw new Error('Shop domain is required but not provided');
      }

      // Build request body for unified recommendation API
      const requestBody = {
        shop_domain: shopDomain,
        context: context,
        limit: limit
      };

      // Add optional fields if available
      if (productIds) requestBody.product_ids = productIds.map(id => String(id)); // Convert all product IDs to strings
      if (customerId) requestBody.user_id = String(customerId); // Convert to string as backend expects string
      if (window.sessionId) requestBody.session_id = String(window.sessionId); // Add session ID for session-based recommendations

      const apiUrl = `${this.baseUrl}/api/v1/recommendations`;
      console.log('🌐 Fetching recommendations from unified API:', apiUrl);
      console.log('📦 Request body:', requestBody);
      console.log('🔗 Backend URL:', this.baseUrl);

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      console.log('Recommendations received from unified API:', data);

      if (data.success && data.recommendations && data.recommendations.length > 0) {
        // Backend provides complete product data via webhooks - no need for additional API calls
        console.log('Using recommendations directly from unified backend:', data.recommendations);
        return data.recommendations;
      } else {
        console.log('No recommendations available from unified API');
        return [];
      }
    } catch (error) {
      console.error('Error fetching recommendations from unified API:', error);
      return [];
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

      console.log('Cart API payload:', cartPayload);

      const response = await fetch('/cart/add.js', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cartPayload)
      });

      if (!response.ok) {
        throw new Error(`Cart API error: ${response.status}`);
      }

      const data = await response.json();
      console.log('Added to cart:', data);

      // Dispatch custom event for theme compatibility
      window.dispatchEvent(new CustomEvent('cart:updated', { detail: data }));

      return data;
    } catch (error) {
      console.error('Error adding to cart:', error);
      throw error;
    }
  }
}

// Export for use in other files
window.RecommendationAPI = RecommendationAPI;
