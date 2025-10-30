// API client for recommendation endpoints

import { BACKEND_URL } from "../utils/constant";
import { type Logger, logger } from "../utils/logger";

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
  image: {
    url: string;
    alt_text?: string;
  } | null;
  images?: Array<{
    url: string;
    alt_text?: string;
    type?: string;
    position?: number;
  }>;
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

export class RecommendationApiClient {
  private baseUrl: string;
  private logger: Logger;
  private makeAuthenticatedRequest:
    | ((url: string, options?: RequestInit) => Promise<Response>)
    | null = null;

  constructor() {
    this.baseUrl = BACKEND_URL;
    this.logger = logger;
  }

  /**
   * Set JWT authentication function
   */
  setJWT(
    makeAuthenticatedRequest: (
      url: string,
      options?: RequestInit,
    ) => Promise<Response>,
  ): void {
    this.makeAuthenticatedRequest = makeAuthenticatedRequest;
  }

  async getRecommendations(
    request: RecommendationRequest,
  ): Promise<RecommendationResponse> {
    try {
      // Check if JWT authentication is available
      if (!this.makeAuthenticatedRequest) {
        throw new Error("JWT authentication not initialized");
      }

      // Use JWT authentication for the request
      const response = await this.makeAuthenticatedRequest(
        `${this.baseUrl}/api/v1/recommendations`,
        {
          method: "POST",
          body: JSON.stringify(request),
        },
      );

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error("Services suspended");
        }
        this.logger.error(
          {
            error: new Error(`HTTP error! status: ${response.status}`),
            shop_domain: request.shop_domain,
          },
          "Failed to fetch recommendations",
        );
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      this.logger.error(
        {
          error: error instanceof Error ? error.message : String(error),
          shop_domain: request.shop_domain,
        },
        "Failed to fetch recommendations",
      );
      throw error;
    }
  }
}

// Default instance
export const recommendationApi = new RecommendationApiClient();
