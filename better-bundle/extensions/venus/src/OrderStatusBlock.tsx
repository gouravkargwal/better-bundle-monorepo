import {
  BlockStack,
  reactExtension,
  Divider,
  useAuthenticatedAccountCustomer,
  useShop,
  TextBlock,
  SkeletonText,
} from "@shopify/ui-extensions-react/customer-account";
import { useState, useEffect, useMemo } from "react";
import {
  recommendationApi,
  type ProductRecommendation,
} from "./api/recommendations";
import { analyticsApi, type ViewedProduct } from "./api/analytics";
import { ProductGrid } from "./components/ProductGrid";
import { SkeletonGrid } from "./components/SkeletonGrid";

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

export default reactExtension(
  "customer-account.order-status.block.render",
  () => <OrderStatusWithRecommendations />,
);

function OrderStatusWithRecommendations() {
  const { id: customerId } = useAuthenticatedAccountCustomer();
  const { myshopifyDomain } = useShop();
  const [loading, setLoading] = useState(true);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(
    () =>
      `venus_order_status_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
  );

  // Memoized column configuration for better performance
  const columnConfig = useMemo(
    () => ({
      extraSmall: 1, // 1 column on very small screens
      small: 2, // 2 columns on small screens
      medium: 2, // 3 columns on medium screens
      large: 2, // 3 columns on large screens (as requested)
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
        context: "order_status",
        metadata: { source: "order_status_recommendation" },
      });

      // Add attribution parameters to track recommendation source
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
      // Note: In order status context, we might need different navigation approach
      console.log(
        "Order status recommendation clicked:",
        productUrlWithAttribution,
      );
    } catch (error) {
      console.error("Failed to track order status click:", error);
    }
  };

  // Fetch recommendations for order status context
  useEffect(() => {
    const fetchRecommendations = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await recommendationApi.getRecommendations({
          context: "order_status",
          limit: 3, // Show 3 products on large screens
          user_id: customerId,
          shop_domain: myshopifyDomain,
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

          // Create recommendation session with viewed products
          const viewedProducts: ViewedProduct[] = transformedProducts.map(
            (product, index) => ({
              product_id: product.id,
              position: index + 1,
            }),
          );

          await analyticsApi.createSession({
            extension_type: "venus",
            context: "order_status",
            user_id: customerId,
            session_id: sessionId,
            viewed_products: viewedProducts,
            metadata: { source: "order_status_page" },
          });
        } else {
          throw new Error("Failed to fetch order status recommendations");
        }
      } catch (err) {
        console.error("Error fetching order status recommendations:", err);
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
        <Divider />
        <BlockStack spacing="tight">
          <SkeletonText size="large" />
          <SkeletonText size="medium" />
        </BlockStack>
        <SkeletonGrid columns={columnConfig} count={3} />
      </BlockStack>
    );
  }

  // Don't render recommendations if there's an error or no products
  if (error || products.length === 0) {
    return (
      <BlockStack spacing="base">
        <Divider />
      </BlockStack>
    );
  }

  return (
    <BlockStack spacing="base">
      <Divider />
      <BlockStack spacing="tight">
        <TextBlock size="large" emphasis="bold">
          You Might Also Like
        </TextBlock>
        <TextBlock appearance="subdued">
          Discover more products based on your order
        </TextBlock>
      </BlockStack>
      <ProductGrid
        products={products}
        onShopNow={trackRecommendationClick}
        columns={columnConfig}
      />
    </BlockStack>
  );
}
