import { useCallback, useState, useEffect } from "react";
import type {
  ProductRecommendationAPI,
  ProductVariant,
  UseVariantManagementReturn,
} from "./types";
import { apolloAnalytics } from "./api/analytics";

export const useVariantManagement = (): UseVariantManagementReturn => {
  const getVariantById = useCallback(
    (
      product: ProductRecommendationAPI,
      variantId: string,
    ): ProductVariant | null => {
      return product.variants.find((v) => v.variant_id === variantId) || null;
    },
    [],
  );

  const isVariantAvailable = useCallback(
    (variant: ProductVariant | null): boolean => {
      return variant ? variant.inventory > 0 : false;
    },
    [],
  );

  const getSelectedOptions = useCallback(
    (variant: ProductVariant): Record<string, string> => {
      // Parse variant title like "S / Green" or "Pink / Medium"
      const options: Record<string, string> = {};
      const parts = variant.title.split(" / ");
      return parts.reduce((acc, part, index) => {
        acc[`option${index + 1}`] = part.trim();
        return acc;
      }, options);
    },
    [],
  );

  return {
    getVariantById,
    isVariantAvailable,
    getSelectedOptions,
  };
};

export const useRecommendationViewTracking = (
  shopDomain: string,
  sessionId: string,
  customerId: string,
  orderId: string,
  recommendations: ProductRecommendationAPI[],
  source: string,
) => {
  const [tracked, setTracked] = useState(false);

  useEffect(() => {
    if (!shopDomain || !sessionId || recommendations.length === 0 || tracked) {
      return;
    }

    const trackViews = async () => {
      try {
        // Track view for each recommendation
        const trackingPromises = recommendations.map((product, index) =>
          apolloAnalytics.trackRecommendationView(
            shopDomain,
            sessionId,
            product.id,
            index + 1, // position
            {
              source: "apollo_post_purchase",
              customer_id: customerId,
              order_id: orderId,
              product_title: product.title,
              product_handle: product.handle,
              price: product.price.amount,
              currency: product.price.currency_code,
              variant_id: product.selectedVariantId,
              score: product.score,
            },
          ),
        );

        await Promise.all(trackingPromises);
        setTracked(true);
        console.log(
          "Apollo: Tracked views for",
          recommendations.length,
          "recommendations",
        );
      } catch (error) {
        console.error("Apollo: Failed to track recommendation views:", error);
      }
    };

    trackViews();
  }, [
    recommendations,
    shopDomain,
    sessionId,
    customerId,
    orderId,
    source,
    tracked,
  ]);

  return tracked;
};
