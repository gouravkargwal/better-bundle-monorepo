import {
  BlockStack,
  TextBlock,
  useApi,
  InlineStack,
} from "@shopify/ui-extensions-react/customer-account";
import { useState, useEffect, useCallback, memo } from "react";
import {
  recommendationApi,
  type ProductRecommendation,
} from "../api/recommendations";
import { ProductCard } from "./ProductCard";

interface ProductRecommendationsProps {
  context?:
    | "product_page"
    | "homepage"
    | "cart"
    | "profile"
    | "checkout"
    | "order_history"
    | "order_status";
  productId?: string;
  category?: string;
  limit?: number;
  title?: string;
  shopDomain?: string;
  customerId?: string;
}

const ProductRecommendations = memo(function ProductRecommendations({
  context = "profile",
  productId,
  category,
  limit = 6,
  title,
  shopDomain,
  customerId,
}: ProductRecommendationsProps) {
  const { i18n } = useApi();
  const [recommendations, setRecommendations] = useState<
    ProductRecommendation[]
  >([]);
  const [loading, setLoading] = useState(true);

  // Debug logging
  console.log("ProductRecommendations component initialized:", {
    context,
    productId,
    category,
    limit,
    shopDomain,
    customerId,
  });

  const loadRecommendations = useCallback(async () => {
    console.log("🚀 loadRecommendations called with:", {
      shopDomain,
      customerId,
      context,
      productId,
      category,
      limit,
    });

    try {
      setLoading(true);

      // shopDomain is now optional - backend will handle lookup from customerId
      if (!shopDomain && !customerId) {
        console.error("❌ Neither shop domain nor customer ID available");
        throw new Error("Shop domain or customer ID required");
      }

      console.log("📡 Making API call to recommendations endpoint...");
      console.log("📡 API Request payload:", {
        shop_domain: shopDomain,
        context,
        product_id: productId,
        user_id: customerId,
        category,
        limit,
        metadata: {
          extension: "venus",
          timestamp: new Date().toISOString(),
        },
      });

      const response = await recommendationApi.getRecommendations({
        shop_domain: shopDomain,
        context,
        product_id: productId,
        user_id: customerId,
        category,
        limit,
        metadata: {
          extension: "venus",
          timestamp: new Date().toISOString(),
        },
      });

      console.log("📥 API response received:", {
        success: response.success,
        recommendationsCount: response.recommendations?.length || 0,
        response: response,
      });

      if (
        response.success &&
        response.recommendations &&
        response.recommendations.length > 0
      ) {
        console.log("✅ Setting recommendations:", response.recommendations);
        setRecommendations(response.recommendations);
      } else {
        console.log("⚠️ No recommendations to show");
        setRecommendations([]);
      }
    } catch (err) {
      console.error("❌ Failed to load recommendations:", err);
      setRecommendations([]);
    } finally {
      console.log("🏁 loadRecommendations completed, setting loading to false");
      setLoading(false);
    }
  }, [context, productId, category, limit, shopDomain, customerId]);

  useEffect(() => {
    console.log("🔄 useEffect triggered, calling loadRecommendations");
    loadRecommendations();
  }, [loadRecommendations]);

  const handleAddToCart = (productId: string) => {
    // Navigate to product page or add to cart
    // This would typically open the product in a new tab or navigate to it
    console.log("Navigate to product:", productId);
  };

  // Only render when we have successful recommendations
  console.log("🎨 Rendering ProductRecommendations:", {
    loading,
    recommendationsCount: recommendations.length,
    willRender: !loading && recommendations.length > 0,
  });

  if (loading || recommendations.length === 0) {
    console.log(
      "🚫 Not rendering - loading:",
      loading,
      "recommendations:",
      recommendations.length,
    );
    return null;
  }

  return (
    <BlockStack spacing="base">
      <TextBlock size="large" emphasis="bold">
        {title || i18n.translate("recommendedForYou")}
      </TextBlock>

      <InlineStack spacing="base" blockAlignment="center">
        {recommendations.map((product, index) => (
          <ProductCard
            key={index}
            product={product}
            onAddToCart={handleAddToCart}
          />
        ))}
      </InlineStack>
    </BlockStack>
  );
});

export { ProductRecommendations };
