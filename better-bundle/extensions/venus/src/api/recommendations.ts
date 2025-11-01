// API client for recommendation endpoints

import { BACKEND_URL } from "../config/constants";
import { logger } from "../utils/logger";
import { makeAuthenticatedRequest } from "../utils/jwt";

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

/**
 * Get recommendations
 */
export const getRecommendations = async (
  storage,
  request: RecommendationRequest,
): Promise<RecommendationResponse> => {
  try {
    if (!storage) {
      throw new Error("Storage is required");
    }

    if (!request.shop_domain) {
      throw new Error("shop_domain is required");
    }

    // ✅ Use makeAuthenticatedRequest for automatic token refresh
    // customerId (user_id) can be null for guest checkouts
    const response = await makeAuthenticatedRequest(
      storage,
      `${BACKEND_URL}/api/v1/recommendations`,
      {
        method: "POST",
        shopDomain: request.shop_domain,
        customerId: request.user_id || undefined, // Pass undefined instead of null
        body: JSON.stringify(request),
      },
    );

    if (!response.ok) {
      if (response.status === 403) {
        throw new Error("Services suspended");
      }
      logger.error(
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
    logger.error(
      {
        error: error instanceof Error ? error.message : String(error),
        shop_domain: request.shop_domain,
      },
      "Failed to fetch Mercury recommendations",
    );
    throw error;
  }
};
