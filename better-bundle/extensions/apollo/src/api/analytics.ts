import { BACKEND_URL } from "../constant";
import type {
  InteractionType,
  UnifiedInteractionRequest,
  UnifiedResponse,
} from "../types";
import { type Logger, logger } from "../utils/logger";
import type { JWTManager } from "../utils/jwtManager";

class ApolloAnalyticsClient {
  private baseUrl: string;
  private logger: Logger;
  private jwtManager: JWTManager | null = null;

  constructor() {
    this.baseUrl = BACKEND_URL as string;
    this.logger = logger;
  }

  setJWTManager(jwtManager: JWTManager) {
    this.jwtManager = jwtManager;
  }

  private async trackInteraction(
    sessionId: string,
    shopDomain: string,
    interactionType: InteractionType,
    productId?: string,
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    try {
      if (!this.jwtManager) {
        throw new Error("JWT Manager not initialized");
      }

      const url = `${this.baseUrl}/api/apollo/track-interaction`;

      const request: UnifiedInteractionRequest = {
        session_id: sessionId,
        shop_domain: shopDomain,
        context: "post_purchase",
        interaction_type: interactionType,
        product_id: productId ? String(productId) : undefined,
        metadata: metadata || {},
      };

      const response = await this.jwtManager.makeAuthenticatedRequest(url, {
        method: "POST",
        body: JSON.stringify(request),
        keepalive: true,
        shopDomain: shopDomain,
        customerId: metadata?.customer_id,
      });

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error("Services suspended");
        }
        this.logger.error(
          {
            error: new Error(`Interaction tracking failed: ${response.status}`),
            shop_domain: shopDomain,
            interactionType,
            productId,
            metadata,
          },
          "Interaction tracking failed",
        );
        throw new Error(`Interaction tracking failed: ${response.status}`);
      }

      const result: UnifiedResponse = await response.json();

      if (result.success) {
        if (result.session_recovery) {
          localStorage.setItem(
            "unified_session_id",
            result.session_recovery.new_session_id,
          );
        }
        return true;
      } else {
        this.logger.error(
          {
            error: new Error(result.message || "Failed to track interaction"),
            shop_domain: shopDomain,
            interactionType,
            productId,
            metadata,
          },
          "Failed to track interaction",
        );
        throw new Error(result.message || "Failed to track interaction");
      }
    } catch (error) {
      this.logger.error(
        {
          error: error instanceof Error ? error.message : String(error),
          shop_domain: shopDomain,
          interactionType,
          productId,
          metadata,
        },
        "Interaction tracking error",
      );
      return false;
    }
  }

  async trackRecommendationView(
    shopDomain: string,
    sessionId: string,
    productId: string,
    position: number,
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    return this.trackInteraction(
      sessionId,
      shopDomain,
      "recommendation_viewed",
      productId,
      {
        extension_type: "apollo",
        source: "apollo_post_purchase",
        data: {
          product: {
            id: productId,
            title: metadata?.product_title || "",
            price: metadata?.product_price || 0,
            type: metadata?.product_type || "",
            vendor: metadata?.product_vendor || "",
            url: metadata?.product_url || "",
          },
          type: "recommendation",
          position: position,
          widget: "apollo_recommendation",
          algorithm: "apollo_algorithm",
          confidence: metadata?.recommendation_confidence || 0.0,
          pageUrl: metadata?.page_url || "",
        },
        ...metadata,
      },
    );
  }

  async trackRecommendationClick(
    shopDomain: string,
    sessionId: string,
    productId: string,
    position: number,
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    return this.trackInteraction(
      sessionId,
      shopDomain,
      "recommendation_clicked",
      productId,
      {
        extension_type: "apollo",
        source: "apollo_post_purchase",
        data: {
          product: {
            id: productId,
            title: metadata?.product_title || "",
            price: metadata?.product_price || 0,
            type: metadata?.product_type || "",
            vendor: metadata?.product_vendor || "",
            url: metadata?.product_url || "",
          },
          type: "recommendation",
          position: position,
          widget: "apollo_recommendation",
          algorithm: "apollo_algorithm",
          confidence: metadata?.recommendation_confidence || 0.0,
          pageUrl: metadata?.page_url || "",
        },
        ...metadata,
      },
    );
  }

  async trackAddToOrder(
    shopDomain: string,
    sessionId: string,
    productId: string,
    variantId: string,
    position: number,
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    return this.trackInteraction(
      sessionId,
      shopDomain,
      "recommendation_add_to_cart",
      productId,
      {
        extension_type: "apollo",
        source: "apollo_post_purchase",
        data: {
          cartLine: {
            merchandise: {
              id: variantId,
              product: {
                id: productId,
              },
            },
            quantity: metadata?.quantity || 1,
          },
          type: "recommendation",
          position: position,
          widget: "apollo_recommendation",
          algorithm: "apollo_algorithm",
        },
        action: "add_to_order_success",
        changeset_applied: true,
        ...metadata,
      },
    );
  }

  async trackRecommendationDecline(
    shopDomain: string,
    sessionId: string,
    productId: string,
    position: number,
    productData?: any,
    metadata?: Record<string, any>,
  ): Promise<boolean> {
    return this.trackInteraction(
      sessionId,
      shopDomain,
      "recommendation_declined",
      productId,
      {
        extension_type: "apollo",
        source: "apollo_post_purchase",
        data: {
          product: {
            id: productId,
            title: productData?.title || "",
            price: productData?.price?.amount || 0,
            type: productData?.product_type || "",
            vendor: productData?.vendor || "",
          },
          type: "recommendation",
          position: position,
          widget: "apollo_recommendation",
          algorithm: "apollo_algorithm",
          confidence: productData?.score || 0.0,
          decline_reason: metadata?.decline_reason || "user_declined",
        },
        action: "recommendation_declined",
        ...metadata,
      },
    );
  }
}

export const apolloAnalytics = new ApolloAnalyticsClient();
