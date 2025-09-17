// API client for recommendation endpoints

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
  | "profile"
  | "order_status"
  | "order_history";

export interface RecommendationRequest {
  shop_domain?: string;
  context: ExtensionContext;
  product_id?: string;
  user_id?: string;
  session_id?: string;
  category?: string;
  limit?: number;
  metadata?: Record<string, any>;
}

export interface ProductRecommendation {
  id: string;
  title: string;
  handle: string;
  description?: string;
  price: {
    amount: string;
    currency_code: string;
  };
  compare_at_price?: {
    amount: string;
    currency_code: string;
  };
  image?: {
    url: string;
    alt_text?: string;
  };
  vendor?: string;
  product_type?: string;
  tags?: string[];
  available?: boolean;
  score?: number;
  url?: string;
  variant_id?: string;
  variants?: any[];
}

export interface RecommendationResponse {
  success: boolean;
  recommendations: ProductRecommendation[];
  count: number;
  source: string;
  context: string;
  timestamp: string;
}

const RECOMMENDATION_API_BASE =
  "https://d242bda5e5c7.ngrok-free.app/api/v1/recommendations";

export class RecommendationApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = RECOMMENDATION_API_BASE) {
    this.baseUrl = baseUrl;
  }

  async getRecommendations(
    request: RecommendationRequest,
  ): Promise<RecommendationResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error("Failed to fetch recommendations:", error);
      throw error;
    }
  }

  async getHealthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      return response.ok;
    } catch (error) {
      console.error("Health check failed:", error);
      return false;
    }
  }

  // Analytics methods moved to separate service: /api/analytics.ts
}

// Default instance
export const recommendationApi = new RecommendationApiClient();
