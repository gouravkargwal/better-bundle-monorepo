import { BACKEND_URL } from "../constant";
import type { ProductRecommendation, CombinedAPIResponse } from "../types";
import { type Logger, logger } from "../utils/logger";

class ApolloRecommendationClient {
  private baseUrl: string;
  private logger: Logger;

  constructor() {
    this.baseUrl = BACKEND_URL as string;
    this.logger = logger;
  }

  async getSessionAndRecommendations(
    shopDomain: string,
    customerId?: string,
    orderId?: string,
    purchasedProductIds?: string[],
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
        customer_id: customerId ? String(customerId) : null,
        browser_session_id: undefined,
        client_id: undefined,
        user_agent:
          typeof navigator !== "undefined" ? navigator.userAgent : undefined,
        ip_address: undefined,
        referrer:
          typeof document !== "undefined" ? document.referrer : undefined,
        page_url:
          typeof window !== "undefined" ? window.location.href : undefined,

        // Recommendation fields
        order_id: orderId ? String(orderId) : null,
        purchased_products: purchasedProductIds || [],
        limit: Math.min(Math.max(limit, 1), 3),

        // Additional metadata
        metadata: {
          extension_type: "apollo",
          source: "apollo_post_purchase",
          ...metadata,
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
        const errorText = await response.text();
        this.logger.error(
          {
            error: new Error(
              `API call failed with status ${response.status}: ${errorText}`,
            ),
            shop_domain: shopDomain,
            customerId,
            orderId,
            purchasedProductIds,
          },
          "Failed to get session and recommendations",
        );
        throw new Error(
          `API call failed with status ${response.status}: ${errorText}`,
        );
      }

      const result: CombinedAPIResponse = await response.json();

      if (!result.success) {
        this.logger.error(
          {
            error: new Error(result.message || "API returned success: false"),
            shop_domain: shopDomain,
            customerId,
            orderId,
            purchasedProductIds,
          },
          "Failed to get session and recommendations",
        );
        throw new Error(result.message || "API returned success: false");
      }

      if (!result.session_data || !result.session_data.session_id) {
        this.logger.error(
          {
            error: new Error("Invalid response: missing session data"),
            shop_domain: shopDomain,
            customerId,
            orderId,
            purchasedProductIds,
          },
          "Invalid response: missing session data",
        );
        throw new Error("Invalid response: missing session data");
      }

      return {
        sessionId: result.session_data.session_id,
        recommendations: result.recommendations || [],
        success: true,
      };
    } catch (error) {
      this.logger.error(
        {
          error: error instanceof Error ? error.message : String(error),
          shop_domain: shopDomain,
          customerId,
          orderId,
          purchasedProductIds,
        },
        "Failed to get session and recommendations",
      );

      return {
        sessionId: "",
        recommendations: [],
        success: false,
        error:
          error instanceof Error ? error.message : "Unknown error occurred",
      };
    }
  }
}

export const apolloRecommendationApi = new ApolloRecommendationClient();
