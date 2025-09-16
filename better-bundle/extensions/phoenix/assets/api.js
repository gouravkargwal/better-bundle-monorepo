// API client for recommendation and product data

class RecommendationAPI {
  constructor() {
    // Use your backend URL - fixed value from extension
    this.baseUrl = "https://d242bda5e5c7.ngrok-free.app";
    this.shopifyBaseUrl = window.location.origin; // For Shopify API calls
  }


  // Fetch recommendations from your API
  async fetchRecommendations(productIds, customerId, limit = 4) {
    try {
      const context = 'cart';
      const shopDomain = window.shopDomain || '';

      // Debug logging
      console.log('🔍 Debug info:', {
        shopDomain: shopDomain,
        productIds: productIds,
        customerId: customerId,
        limit: limit
      });

      // Validate required fields
      if (!shopDomain) {
        throw new Error('Shop domain is required but not provided');
      }

      // Build request body according to your RecommendationRequest model
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
      console.log('🌐 Fetching recommendations from:', apiUrl);
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
      console.log('Recommendations received:', data);

      if (data.success && data.recommendations && data.recommendations.length > 0) {
        // Backend provides complete product data via webhooks - no need for additional API calls
        console.log('Using recommendations directly from backend:', data.recommendations);
        return data.recommendations;
      } else {
        console.log('No recommendations available');
        return [];
      }
    } catch (error) {
      console.error('Error fetching recommendations:', error);
      return [];
    }
  }

  // Add product to cart using Shopify's native Cart AJAX API
  async addToCart(variantId, quantity = 1) {
    try {
      const response = await fetch('/cart/add.js', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items: [
            {
              id: variantId,
              quantity: quantity
            }
          ]
        })
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
