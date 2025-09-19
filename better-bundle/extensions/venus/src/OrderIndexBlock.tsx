import React from "react";
import {
  BlockStack,
  reactExtension,
  TextBlock,
  useAuthenticatedAccountCustomer,
  useNavigation,
  SkeletonText,
} from "@shopify/ui-extensions-react/customer-account";
import { ProductGrid } from "./components/ProductGrid";
import { SkeletonGrid } from "./components/SkeletonGrid";
import { useRecommendations } from "./hooks/useRecommendations";
import { analyticsApi } from "./api/analytics";

export default reactExtension(
  "customer-account.order-index.block.render",
  () => <OrderIndexWithRecommendations />,
);

function OrderIndexWithRecommendations() {
  const { id: customerId } = useAuthenticatedAccountCustomer();
  const { navigate } = useNavigation();

  // Track extension activity when component mounts
  React.useEffect(() => {
    if (customerId) {
      analyticsApi
        .trackExtensionLoad(
          customerId,
          "customer_account_order_index_block_render",
          "order-index-page",
        )
        .catch((error) => {
          console.warn("Failed to track Venus extension activity:", error);
        });
    }
  }, [customerId]);

  const { loading, products, error, trackRecommendationClick, columnConfig } =
    useRecommendations({
      context: "order_history",
      limit: 6,
      customerId,
      columnConfig: {
        extraSmall: 1, // 1 column on very small screens
        small: 2, // 2 columns on small screens
        medium: 3, // 3 columns on medium screens
        large: 3, // 3 columns on large screens
      },
    });

  // Override trackRecommendationClick to include navigation
  const handleShopNow = async (
    productId: string,
    position: number,
    productUrl: string,
  ) => {
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
        <BlockStack spacing="tight">
          <SkeletonText size="large" />
          <SkeletonText size="medium" />
        </BlockStack>
        <SkeletonGrid columns={columnConfig} count={6} />
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
        onShopNow={handleShopNow}
        columns={columnConfig}
      />
    </BlockStack>
  );
}
