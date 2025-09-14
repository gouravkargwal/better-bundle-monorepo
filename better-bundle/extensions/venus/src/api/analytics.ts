/**
 * Analytics API Client for BetterBundle Venus Extension
 *
 * This client handles all analytics and attribution tracking separately from recommendations.
 * Follows proper separation of concerns and single responsibility principle.
 */

export interface AttributionData {
  session_id: string;
  product_id: string;
  extension_type: string;
  context: string;
  position: number;
  timestamp: string;
}

export interface ViewedProduct {
  product_id: string;
  position: number;
}

export interface SessionData {
  shop_id?: string;
  extension_type: string;
  context: string;
  user_id?: string;
  session_id: string;
  viewed_products?: ViewedProduct[];
  metadata?: Record<string, any>;
}

export interface InteractionData {
  session_id: string;
  product_id: string;
  interaction_type: "view" | "click" | "add_to_cart" | "buy_now" | "shop_now" | "purchase";
  position?: number;
  extension_type: string;
  context: string;
  metadata?: Record<string, any>;
}

export interface AttributionResponse {
  success: boolean;
  message: string;
  data?: Record<string, any>;
}

export interface MetricsResponse {
  success: boolean;
  metrics?: {
    total_revenue: number;
    total_attributions: number;
    average_confidence: number;
    extension_breakdown: Record<string, { count: number; revenue: number }>;
    date_range: {
      start: string;
      end: string;
    };
  };
  error?: string;
}

class AnalyticsApiClient {
  private baseUrl: string;

  constructor() {
    // Use the analytics service URL
    this.baseUrl = "https://c28c503b2040.ngrok-free.app/api/v1/analytics";
  }

  /**
   * Create a new recommendation session for tracking
   */
  async createSession(sessionData: SessionData): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/session`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(sessionData),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result: AttributionResponse = await response.json();
      return result.success;
    } catch (error) {
      console.error("Failed to create analytics session:", error);
      return false;
    }
  }

  /**
   * Track a recommendation interaction
   */
  async trackInteraction(interactionData: InteractionData): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/interaction`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(interactionData),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result: AttributionResponse = await response.json();
      return result.success;
    } catch (error) {
      console.error("Failed to track interaction:", error);
      return false;
    }
  }

  /**
   * Get attribution metrics for a shop
   */
  async getMetrics(
    shopId: string,
    startDate?: string,
    endDate?: string,
    extensionType?: string,
  ): Promise<MetricsResponse> {
    try {
      const params = new URLSearchParams();
      if (startDate) params.append("start_date", startDate);
      if (endDate) params.append("end_date", endDate);
      if (extensionType) params.append("extension_type", extensionType);

      const response = await fetch(
        `${this.baseUrl}/metrics/${shopId}?${params.toString()}`,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        },
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("Failed to get analytics metrics:", error);
      return { success: false, error: String(error) };
    }
  }

  /**
   * Health check for analytics service
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      return response.ok;
    } catch (error) {
      console.error("Analytics health check failed:", error);
      return false;
    }
  }

  /**
   * Store attribution data in cart attributes for order processing
   */
  async storeCartAttribution(
    attributionData: AttributionData,
  ): Promise<boolean> {
    try {
      const response = await fetch("/cart/update.js", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          attributes: {
            bb_recommendation_session_id: attributionData.session_id,
            bb_recommendation_product_id: attributionData.product_id,
            bb_recommendation_extension: attributionData.extension_type,
            bb_recommendation_context: attributionData.context,
            bb_recommendation_position: attributionData.position.toString(),
            bb_recommendation_timestamp: attributionData.timestamp,
            bb_recommendation_source: "betterbundle",
          },
        }),
      });

      return response.ok;
    } catch (error) {
      console.error("Failed to store cart attribution:", error);
      return false;
    }
  }
}

// Default instance
export const analyticsApi = new AnalyticsApiClient();
