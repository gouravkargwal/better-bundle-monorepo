/**
 * Recommendation API Client for BetterBundle Apollo Post-Purchase Extension
 *
 * This client handles fetching personalized product recommendations for post-purchase upsells.
 * Designed specifically for Shopify Post-Purchase Extensions.
 */

export type ExtensionContext =
  | "homepage"
  | "product_page"
  | "collection_page"
  | "cart_page"
  | "search_page"
  | "customer_account"
  | "checkout_page"
  | "order_page"
  | "thank_you_page"
  | "post_purchase";

export interface PostPurchaseRecommendationRequest {
  shop_domain?: string;
  context: ExtensionContext;
  order_id?: string;
  customer_id?: string;
  purchased_products?: Array<{
    product_id: string;
    variant_id: string;
    quantity: number;
    price: number;
  }>;
  limit?: number;
  metadata?: Record<string, any>;
}

export interface ProductVariant {
  id: string;
  title: string;
  price: {
    amount: string;
    currency_code: string;
  };
  available: boolean;
  inventory_quantity: number;
}

export interface ProductRecommendation {
  id: string;
  title: string;
  handle: string;
  description?: string;
  image?: {
    url: string;
    alt_text?: string;
  };
  price: {
    amount: string;
    currency_code: string;
  };
  compare_at_price?: {
    amount: string;
    currency_code: string;
  };
  vendor?: string;
  product_type?: string;
  tags?: string[];
  available?: boolean;
  score?: number;
  url?: string;
  variants: ProductVariant[];
  default_variant_id: string;
  reason?: string;
}

export interface PostPurchaseRecommendationResponse {
  success: boolean;
  recommendations: ProductRecommendation[];
  count: number;
  source: string;
  context: string;
  timestamp: string;
  order_id?: string;
  customer_id?: string;
}

class ApolloRecommendationClient {
  private baseUrl: string;

  constructor() {
    // Use the recommendation service URL
    this.baseUrl = "https://036cff6f721b.ngrok-free.app/api/v1/recommendations";
  }

  /**
   * Get post-purchase recommendations based on the completed order
   */
  async getPostPurchaseRecommendations(
    request: PostPurchaseRecommendationRequest,
  ): Promise<PostPurchaseRecommendationResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/post-purchase`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ...request,
          context: "post_purchase", // Always use post_purchase context
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error("Failed to fetch post-purchase recommendations:", error);
      throw error;
    }
  }

  /**
   * Get fallback recommendations when post-purchase specific ones fail
   */
  async getFallbackRecommendations(
    shopDomain: string,
    limit: number = 3,
  ): Promise<ProductRecommendation[]> {
    try {
      const response = await fetch(`${this.baseUrl}/fallback`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_domain: shopDomain,
          context: "post_purchase",
          limit,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data.recommendations || [];
    } catch (error) {
      console.error("Failed to fetch fallback recommendations:", error);
      return [];
    }
  }

  /**
   * Health check for recommendation service
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      return response.ok;
    } catch (error) {
      console.error("Recommendation service health check failed:", error);
      return false;
    }
  }
}

// Default instance
export const apolloRecommendationApi = new ApolloRecommendationClient();
