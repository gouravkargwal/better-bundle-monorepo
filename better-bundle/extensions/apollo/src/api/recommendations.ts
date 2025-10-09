/**
 * Apollo Recommendations API Client - Fixed Version
 *
 * This client handles fetching personalized product recommendations for post-purchase upsells.
 * Designed specifically for Shopify Post-Purchase Extensions.
 *
 * Key Features:
 * - Combined session creation and recommendation fetching in one API call
 * - Proper handling of session data and browser session IDs
 * - Support for user agent, referrer, and page URL tracking
 * - Error handling with detailed logging
 */

// ============================================================================
// TYPES - Match Backend API Response Structure
// ============================================================================

/**
 * Product variant from API response
 * Matches your actual API structure with variant_id, price as number, etc.
 */
export interface ProductVariant {
  variant_id: string;
  title: string;
  price: number;
  compare_at_price: number | null;
  sku: string;
  barcode: string | null;
  inventory: number;
  currency_code: string;
}

/**
 * Product option (Size, Color, etc.)
 */
export interface ProductOption {
  id: string;
  name: string;
  position: number;
  values: string[];
}

/**
 * Product recommendation from API response
 * Matches the exact structure from your JSON response
 */
export interface ProductRecommendation {
  id: string;
  title: string;
  handle: string;
  url: string;
  price: {
    amount: string;
    currency_code: string;
  };
  image: string | null;
  vendor: string;
  product_type: string;
  available: boolean;
  score: number;
  variant_id: string;
  selectedVariantId: string;
  variants: ProductVariant[];
  options: ProductOption[];
  inventory: number;
  // Optional fields
  compare_at_price?: {
    amount: string;
    currency_code: string;
  };
  description?: string;
  tags?: string[];
  reason?: string;
  // Post-purchase compliance fields
  requires_shipping?: boolean;
  subscription?: boolean;
  selling_plan?: any;
}

/**
 * Session data from API response
 */
export interface SessionData {
  session_id: string;
  customer_id: string | null;
  client_id: string | null;
  created_at: string;
  expires_at: string | null;
}

/**
 * API Response structure
 */
export interface CombinedAPIResponse {
  success: boolean;
  message: string;
  session_data: SessionData;
  recommendations: ProductRecommendation[];
  recommendation_count: number;
}

// ============================================================================
// APOLLO RECOMMENDATIONS CLIENT
// ============================================================================

class ApolloRecommendationClient {
  private baseUrl: string;

  constructor() {
    // Use the unified analytics service URL
    this.baseUrl = "https://c5da58a2ed7b.ngrok-free.app";
  }

  /**
   * Get session and recommendations in a single optimized API call
   * This is the primary method for Apollo post-purchase extensions
   *
   * @param shopDomain - Shop domain (e.g., "mystore.myshopify.com")
   * @param customerId - Customer ID (optional)
   * @param orderId - Order ID for post-purchase context
   * @param purchasedProductIds - Array of product IDs that were just purchased
   * @param limit - Number of recommendations to return (default: 3, max: 10)
   * @param metadata - Additional metadata to pass to the backend
   */
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

      // Build the request payload matching backend expectations
      const payload = {
        // Session creation fields
        shop_domain: shopDomain,
        customer_id: customerId ? String(customerId) : null, // ✅ Convert to string
        browser_session_id: undefined, // Post-purchase doesn't have browser session
        client_id: undefined, // Post-purchase doesn't have client_id
        user_agent:
          typeof navigator !== "undefined" ? navigator.userAgent : undefined,
        ip_address: undefined, // Backend will extract from request
        referrer:
          typeof document !== "undefined" ? document.referrer : undefined,
        page_url:
          typeof window !== "undefined" ? window.location.href : undefined,

        // Recommendation fields
        order_id: orderId ? String(orderId) : null, // ✅ Convert to string
        purchased_products: purchasedProductIds || [], // Backend expects product_ids array
        limit: Math.min(Math.max(limit, 1), 10), // Clamp between 1-10

        // Additional metadata
        metadata: {
          extension_type: "apollo",
          source: "apollo_post_purchase",
          ...metadata,
        },
      };

      console.log("🚀 Apollo: Fetching session + recommendations", {
        shopDomain,
        customerId,
        orderId,
        productCount: purchasedProductIds?.length,
        limit,
      });

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
        keepalive: true, // Ensures request completes even if page unloads
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          `API call failed with status ${response.status}: ${errorText}`,
        );
      }

      const result: CombinedAPIResponse = await response.json();

      // Validate response structure
      if (!result.success) {
        throw new Error(result.message || "API returned success: false");
      }

      if (!result.session_data || !result.session_data.session_id) {
        throw new Error("Invalid response: missing session data");
      }

      console.log(
        "✅ Apollo: Session + recommendations retrieved successfully",
        {
          sessionId: result.session_data.session_id,
          recommendationCount: result.recommendation_count,
          customerId: result.session_data.customer_id,
        },
      );

      return {
        sessionId: result.session_data.session_id,
        recommendations: result.recommendations || [],
        success: true,
      };
    } catch (error) {
      console.error("💥 Apollo: Combined API call error:", error);

      // Return error response instead of throwing
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

// ============================================================================
// EXPORT DEFAULT INSTANCE
// ============================================================================

export const apolloRecommendationApi = new ApolloRecommendationClient();
