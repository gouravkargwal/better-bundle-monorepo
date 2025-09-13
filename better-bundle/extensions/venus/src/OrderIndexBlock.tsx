import {
  BlockStack,
  reactExtension,
  TextBlock,
  Banner,
  useApi,
  Divider,
  useAuthenticatedAccountCustomer,
} from "@shopify/ui-extensions-react/customer-account";
import { ProductRecommendations } from "./components/ProductRecommendations";

export default reactExtension(
  "customer-account.order-index.block.render",
  () => <OrderIndexWithRecommendations />,
);

function OrderIndexWithRecommendations() {
  const api = useApi();
  const { id: customerId } = useAuthenticatedAccountCustomer();
  const { i18n } = api;

  return (
    <BlockStack spacing="base">
      {/* Promotional banner for order index */}
      <Banner>
        <BlockStack inlineAlignment="center">
          <TextBlock>{i18n.translate("discoverMoreProducts")}</TextBlock>
        </BlockStack>
      </Banner>

      <Divider />

      {/* Product recommendations optimized for order history context */}
      <ProductRecommendations
        context="order_history"
        title={i18n.translate("trendingInYourOrders")}
        limit={6}
        category="trending"
        customerId={customerId}
      />
    </BlockStack>
  );
}
