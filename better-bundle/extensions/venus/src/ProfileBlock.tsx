import { useEffect } from "react";
import {
  reactExtension,
  TextBlock,
  SkeletonText,
  BlockStack,
  useAuthenticatedAccountCustomer,
  useNavigation,
} from "@shopify/ui-extensions-react/customer-account";
import { ProductGrid } from "./components/ProductGrid";
import { SkeletonGrid } from "./components/SkeletonGrid";
import { useRecommendations } from "./hooks/useRecommendations";

export default reactExtension("customer-account.profile.block.render", () => (
  <ProfileBlock />
));

function ProfileBlock() {
  const { id: customerId } = useAuthenticatedAccountCustomer();
  const { navigate } = useNavigation();

  const {
    loading,
    products,
    error,
    trackRecommendationClick,
    trackRecommendationView,
    columnConfig,
  } = useRecommendations({
    context: "profile",
    limit: 8,
    customerId,
    shopDomain: "",
    columnConfig: {
      extraSmall: 1, // 1 column on very small screens
      small: 2, // 2 columns on small screens
      medium: 3, // 3 columns on medium screens
      large: 4, // 4 columns on large screens
    },
  });

  // Track when recommendations come into view
  useEffect(() => {
    if (!products.length || loading) return;
    trackRecommendationView();
  }, [products, loading, trackRecommendationView]);

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
        onShopNow={handleShopNow}
        columns={columnConfig}
      />
    </BlockStack>
  );
}
