/**
 * Analytics API Client for BetterBundle Phoenix Extension
 * 
 * This client handles all analytics and attribution tracking for the Phoenix extension.
 * Follows the same pattern as Venus extension for consistency.
 */

class AnalyticsApiClient {
  constructor() {
    // Use the same analytics service URL as Venus
    this.baseUrl = "https://d242bda5e5c7.ngrok-free.app/api/v1/analytics";
  }

  /**
   * Create a new recommendation session for tracking
   */
  async createSession(sessionData) {
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

      const result = await response.json();
      return result.success;
    } catch (error) {
      console.error("Failed to create analytics session:", error);
      return false;
    }
  }

  /**
   * Track a recommendation interaction
   */
  async trackInteraction(interactionData) {
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

      const result = await response.json();
      return result.success;
    } catch (error) {
      console.error("Failed to track interaction:", error);
      return false;
    }
  }

  /**
   * Get attribution metrics for a shop
   */
  async getMetrics(shopId, startDate, endDate, extensionType) {
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
  async healthCheck() {
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
  async storeCartAttribution(attributionData) {
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

  /**
   * Generate a short reference ID for attribution URLs
   */
  generateShortRef(sessionId) {
    return sessionId
      .split("")
      .reduce((hash, char) => {
        return ((hash << 5) - hash + char.charCodeAt(0)) & 0xffffffff;
      }, 0)
      .toString(36)
      .substring(0, 6);
  }

  /**
   * Add attribution parameters to product URL
   */
  addAttributionToUrl(productUrl, productId, position, sessionId) {
    const shortRef = this.generateShortRef(sessionId);
    const attributionParams = new URLSearchParams({
      ref: shortRef,
      src: productId,
      pos: position.toString(),
    });

    return `${productUrl}?${attributionParams.toString()}`;
  }
}

// Create global instance
window.analyticsApi = new AnalyticsApiClient();