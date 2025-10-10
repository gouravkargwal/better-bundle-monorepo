export function buildMercuryMetadata(
  checkoutStep,
  cartValue,
  cartItems,
) {
  return {
    mercury_checkout: true,
    checkout_type: "one_page",
    checkout_step: checkoutStep,
    cart_value: cartValue,
    cart_items: cartItems,
    block: "checkout.order-summary.render", // Primary placement for one-page checkout
  };
}

const RECOMMENDATION_API_BASE =
  "https://c5da58a2ed7b.ngrok-free.app/api/v1/recommendations";

export class RecommendationApiClient {
  constructor(baseUrl = RECOMMENDATION_API_BASE) {
    this.baseUrl = baseUrl;
  }

  async getRecommendations(request) {
    try {
      // Ensure Mercury uses single checkout context
      const mercuryRequest = {
        ...request,
        context: "checkout_page", // Force single context for Mercury
        metadata: {
          ...request.metadata,
          ...buildMercuryMetadata(
            request.checkout_step,
            request.cart_value,
            request.cart_items,
          ),
        },
      };

      const response = await fetch(`${this.baseUrl}/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(mercuryRequest),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error("Failed to fetch Mercury recommendations:", error);
      throw error;
    }
  }
}

// Default Mercury instance
export const recommendationApi = new RecommendationApiClient();