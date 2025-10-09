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

export interface RecommendationRequest {
  shop_domain?: string;
  context: ExtensionContext;
  order_id?: string;
  customer_id?: string;
  session_id?: string;
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
  // ✅ SHOPIFY RESTRICTION: Add fields for post-purchase compliance
  requires_shipping?: boolean;
  subscription?: boolean;
  selling_plan?: any;
}

export interface RecommendationResponse {
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
    this.baseUrl = "https://c5da58a2ed7b.ngrok-free.app";
  }

  /**
   * Get session and recommendations in a single optimized API call
   * This is the recommended method for Apollo post-purchase extensions
   */
  async getSessionAndRecommendations(
    shopDomain: string,
    customerId?: string,
    orderId?: string,
    purchasedProducts?: Array<{
      product_id: string;
      variant_id: string;
      quantity: number;
      price: number;
    }>,
    limit: number = 3,
    metadata?: Record<string, any>,
  ): Promise<{
    sessionId: string;
    recommendations: ProductRecommendation[];
    success: boolean;
    error?: string;
  }> {
    try {
      const url = `${this.baseUrl}/api/apollo/get-session-and-recommendations`;

      const payload = {
        shop_domain: shopDomain,
        customer_id: customerId,
        order_id: orderId,
        purchased_products: purchasedProducts,
        limit,
        metadata: {
          ...metadata,
          extension_type: "apollo",
          source: "apollo_post_purchase",
        },
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
        throw new Error(`Combined API call failed: ${response.status}`);
      }

      const result = await response.json();

      if (
        result.success &&
        result.session_data &&
        result.session_data.session_id
      ) {
        console.log(
          "🚀 Apollo: Session + recommendations retrieved in single call",
        );
        console.log(`📊 Recommendations: ${result.recommendation_count} items`);

        return {
          sessionId: result.session_data.session_id,
          recommendations: result.recommendations || [],
          success: true,
        };
      } else {
        throw new Error(
          result.message || "Failed to get session and recommendations",
        );
      }
    } catch (error) {
      console.error("💥 Apollo: Combined API call error:", error);
      return {
        sessionId: "",
        recommendations: [],
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }
}

// Default instance
export const apolloRecommendationApi = new ApolloRecommendationClient();
