class AnalyticsApiClient {
  constructor() {
    this.baseUrl = "https://c5da58a2ed7b.ngrok-free.app";
  }

  async getOrCreateSession(shopDomain, customerId) {
    try {
      const url = `${this.baseUrl}/api/mercury/get-or-create-session`;
      const payload = {
        shop_domain: shopDomain,
        customer_id: customerId,
        user_agent: navigator.userAgent,
        ip_address: undefined,
        referrer: undefined,
      };

      console.log("🌐 Mercury: Creating session with:", {
        shop_domain: shopDomain,
        customer_id: customerId,
      });

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
        keepalive: true,
      });

      if (!response.ok) {
        throw new Error(`Session creation failed: ${response.status}`);
      }

      const result = await response.json();

      if (result.success && result.data && result.data.session_id) {
        const sessionId = result.data.session_id;
        console.log("✅ Mercury: Session created/retrieved:", sessionId);
        return sessionId;
      } else {
        throw new Error(result.message || "Failed to create session");
      }
    } catch (error) {
      console.error("💥 Mercury: Session creation error:", error);
      throw error;
    }
  }

  /**
   * Track interaction using unified analytics
   */
  async trackUnifiedInteraction(request) {
    try {
      const url = `${this.baseUrl}/api/mercury/track-interaction`;
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
        keepalive: true,
      });

      if (!response.ok) {
        throw new Error(`Interaction tracking failed: ${response.status}`);
      }

      const result = await response.json();

      if (result.success) {
        console.log(
          "✅ Mercury interaction tracked:",
          result.data?.interaction_id,
        );
        return true;
      } else {
        throw new Error(result.message || "Failed to track interaction");
      }
    } catch (error) {
      console.error("💥 Mercury interaction tracking error:", error);
      return false;
    }
  }

  buildRecommendationMetadata(params) {
    const {
      extensionType,
      source = "mercury_checkout_extension",
      cartProductCount,
      recommendationCount,
      recommendations,
      widget = "mercury_recommendation",
      algorithm = "mercury_algorithm",
      extra = {},
    } = params;

    // Preserve any extra metadata keys but ensure required structure exists
    return {
      source,
      cart_product_count: cartProductCount ?? extra.cart_product_count ?? 0,
      recommendation_count: recommendationCount,
      extension_type: extensionType,
      data: {
        recommendations: recommendations.map((r) => ({
          id: String(r.id),
          position: r.position,
        })),
        type: "recommendation",
        widget: extra.widget ?? widget,
        algorithm: extra.algorithm ?? algorithm,
      },
      // Spread at the end so callers can add bespoke keys without breaking the schema
      ...extra,
    };
  }

  /**
   * Track recommendation view (when recommendations are displayed)
   */
  async trackRecommendationView(
    shopDomain,
    context,
    sessionId,
    customerId,
    productIds,
    metadata,
  ) {
    try {
      const recommendations = (productIds || []).map((id, index) => ({
        id,
        position: index + 1,
      }));

      const request = {
        session_id: sessionId,
        shop_domain: shopDomain,
        context,
        interaction_type: "recommendation_viewed",
        customer_id: customerId,
        page_url: null,
        referrer: null,
        metadata: this.buildRecommendationMetadata({
          extensionType: "mercury",
          recommendationCount: recommendations.length,
          recommendations,
          cartProductCount: metadata?.cart_product_count,
          extra: metadata,
        }),
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      console.error("Failed to track recommendation view:", error);
      return false;
    }
  }

  /**
   * Track recommendation click (when user clicks on a recommendation)
   */
  async trackRecommendationClick(
    shopDomain,
    context,
    productId,
    position,
    sessionId,
    customerId,
    metadata,
  ) {
    try {
      const request = {
        session_id: sessionId,
        shop_domain: shopDomain,
        context,
        interaction_type: "recommendation_clicked",
        customer_id: customerId,
        product_id: productId,
        page_url: null,
        referrer: null,
        metadata: {
          source: metadata?.source || "mercury_recommendation",
          cart_product_count: metadata?.cart_product_count ?? 0,
          recommendation_count: 1,
          extension_type: "mercury",
          data: {
            product: {
              id: productId,
            },
            position: position,
            type: "recommendation",
            widget: metadata?.widget || "mercury_recommendation",
            algorithm: metadata?.algorithm || "mercury_algorithm",
          },
          ...metadata,
        },
      };

      return await this.trackUnifiedInteraction(request);
    } catch (error) {
      console.error("Failed to track recommendation click:", error);
      return false;
    }
  }
}

// Default instance
export const analyticsApi = new AnalyticsApiClient();