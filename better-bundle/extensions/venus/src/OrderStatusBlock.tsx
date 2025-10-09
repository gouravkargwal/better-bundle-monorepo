import { useEffect } from "react";
import {
  BlockStack,
  reactExtension,
  Divider,
  useAuthenticatedAccountCustomer,
  useShop,
  useNavigation,
  TextBlock,
  SkeletonText,
} from "@shopify/ui-extensions-react/customer-account";
import { ProductGrid } from "./components/ProductGrid";
import { SkeletonGrid } from "./components/SkeletonGrid";
import { useRecommendations } from "./hooks/useRecommendations";

export default reactExtension(
  "customer-account.order-status.block.render",
  () => <OrderStatusWithRecommendations />,
);

function OrderStatusWithRecommendations() {
  const { id: customerId } = useAuthenticatedAccountCustomer();
  const { myshopifyDomain } = useShop();
  const { navigate } = useNavigation();

  const {
    loading,
    products,
    error,
    trackRecommendationClick,
    trackRecommendationView,
    columnConfig,
  } = useRecommendations({
    context: "order_status",
    limit: 2,
    customerId,
    shopDomain: myshopifyDomain,
    columnConfig: {
      extraSmall: 1, // 1 column on very small screens
      small: 2, // 2 columns on small screens
      medium: 2, // 2 columns on medium screens
      large: 2, // 2 columns on large screens
    },
  });

  // Track when recommendations come into view
  useEffect(() => {
    if (!products.length || loading) return;
    console.log("🔍 Venus: Tracking recommendation view");
    trackRecommendationView();
  }, [products, loading, trackRecommendationView]);

  // Override trackRecommendationClick to include navigation
  const handleShopNow = async (
    productId: string,
    position: number,
    productUrl: string,
  ) => {
    console.log("🔍 Venus: Tracking recommendation click");
    const urlWithAttribution = await trackRecommendationClick(
      productId,
      position,
      productUrl,
    );
    // Navigate to product page with attribution parameters immediately
    navigate(urlWithAttribution);
  };

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
        onShopNow={handleShopNow}
        columns={columnConfig}
      />
    </BlockStack>
  );
}
