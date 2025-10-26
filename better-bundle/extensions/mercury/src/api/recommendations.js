import { BACKEND_URL } from "../constant";
import { logger } from "../utils/logger";

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

export class RecommendationApiClient {
  constructor() {
    this.baseUrl = BACKEND_URL;
    this.jwtManager = null;
    this.logger = logger;
  }

  setJWTManager(jwtManager) {
    this.jwtManager = jwtManager;
  }

  async getRecommendations(request) {
    try {
      if (!this.jwtManager) {
        throw new Error("JWT Manager not initialized");
      }

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

      const response = await this.jwtManager.makeAuthenticatedRequest(
        `${this.baseUrl}/api/v1/recommendations`,
        {
          method: "POST",
          body: JSON.stringify(mercuryRequest),
          shopDomain: request.shop_domain,
          customerId: request.user_id,
        }
      );

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error("Services suspended");
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      this.logger.error("Failed to fetch Mercury recommendations:", error);
      throw error;
    }
  }
}

// Default Mercury instance
export const recommendationApi = new RecommendationApiClient();