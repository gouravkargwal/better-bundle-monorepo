import {
  reactExtension,
  TextBlock,
  SkeletonText,
  BlockStack,
  useAuthenticatedAccountCustomer,
  useNavigation,
} from "@shopify/ui-extensions-react/customer-account";
import { useState, useEffect, useMemo } from "react";
import {
  recommendationApi,
  type ProductRecommendation,
} from "./api/recommendations";
import { analyticsApi, type ViewedProduct } from "./api/analytics";
import { ProductGrid } from "./components/ProductGrid";
import { SkeletonGrid } from "./components/SkeletonGrid";

export default reactExtension("customer-account.profile.block.render", () => (
  <ProfileBlock />
));

interface Product {
  id: string;
  title: string;
  handle: string;
  price: string;
  image: string;
  inStock: boolean;
  url: string;
  variant_id?: string;
}

function ProfileBlock() {
  const { id: customerId } = useAuthenticatedAccountCustomer();
  const { navigate } = useNavigation();
  const [loading, setLoading] = useState(true);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(
    () =>
      `venus_profile_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
  );

  // Memoized column configuration for better performance
  const columnConfig = useMemo(
    () => ({
      extraSmall: 1, // 1 column on very small screens
      small: 2, // 2 columns on small screens
      medium: 3, // 3 columns on medium screens
      large: 4, // 4 columns on large screens
    }),
    [],
  );

  const trackRecommendationClick = async (
    productId: string,
    position: number,
    productUrl: string,
  ) => {
    try {
      await analyticsApi.trackInteraction({
        session_id: sessionId,
        product_id: productId,
        interaction_type: "click",
        position,
        extension_type: "venus",
        context: "profile",
        metadata: { source: "view_product_button" },
      });

      // Add attribution parameters to track recommendation source
      // Create a deterministic short reference using a simple hash
      const shortRef = sessionId
        .split("")
        .reduce((hash, char) => {
          return ((hash << 5) - hash + char.charCodeAt(0)) & 0xffffffff;
        }, 0)
        .toString(36)
        .substring(0, 6);

      const attributionParams = new URLSearchParams({
        ref: shortRef,
        src: productId,
        pos: position.toString(),
      });

      // Navigate to product page with attribution
      const productUrlWithAttribution = `${productUrl}?${attributionParams.toString()}`;
      navigate(productUrlWithAttribution);

      console.log(
        "View product tracked and navigating to:",
        productUrlWithAttribution,
      );
    } catch (error) {
      console.error("Failed to track click:", error);
    }
  };

  // Create recommendation session and fetch recommendations
  useEffect(() => {
    const fetchRecommendations = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await recommendationApi.getRecommendations({
          context: "profile",
          limit: 4,
          user_id: customerId,
        });

        if (response.success && response.recommendations) {
          // Transform API response to component format
          const transformedProducts: Product[] = response.recommendations.map(
            (rec: ProductRecommendation) => ({
              id: rec.id,
              title: rec.title,
              handle: rec.handle,
              price: `${rec.price.currency_code} ${rec.price.amount}`,
              image: rec.image?.url,
              inStock: rec.available ?? true,
              url: rec.url,
            }),
          );

          setProducts(transformedProducts);

          // Create recommendation session with viewed products in single call
          const viewedProducts: ViewedProduct[] = transformedProducts.map(
            (product, index) => ({
              product_id: product.id,
              position: index + 1,
            }),
          );

          await analyticsApi.createSession({
            extension_type: "venus",
            context: "profile",
            user_id: customerId,
            session_id: sessionId,
            viewed_products: viewedProducts,
            metadata: { source: "profile_page" },
          });
        } else {
          throw new Error("Failed to fetch recommendations");
        }
      } catch (err) {
        console.error("Error fetching recommendations:", err);
        setError("Failed to load recommendations");
      } finally {
        setLoading(false);
      }
    };

    fetchRecommendations();
  }, [customerId]);

  if (loading) {
    return (
      <BlockStack spacing="base">
        <BlockStack spacing="tight">
          <SkeletonText size="large" />
          <SkeletonText size="medium" />
        </BlockStack>
        <SkeletonGrid columns={columnConfig} count={3} />
      </BlockStack>
    );
  }

  // Don't render anything if there's an error or no products
  if (error || products.length === 0) {
    return null;
  }

  return (
    <BlockStack spacing="base">
      <BlockStack spacing="tight">
        <TextBlock size="large" emphasis="bold">
          Recommended for You
        </TextBlock>
        <TextBlock appearance="subdued">Curated just for you</TextBlock>
      </BlockStack>
      <ProductGrid
        products={products}
        onShopNow={trackRecommendationClick}
        columns={columnConfig}
      />
    </BlockStack>
  );
}
