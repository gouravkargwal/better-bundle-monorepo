import {
  BlockStack,
  reactExtension,
  useApi,
  Divider,
  useAuthenticatedAccountCustomer,
  useShop,
} from "@shopify/ui-extensions-react/customer-account";

export default reactExtension(
  "customer-account.order-status.block.render",
  () => <OrderStatusWithRecommendations />,
);

function OrderStatusWithRecommendations() {
  const { i18n } = useApi();
  const { id: customerId } = useAuthenticatedAccountCustomer();
  const { myshopifyDomain } = useShop();

  return (
    <BlockStack spacing="base">
      <Divider />
    </BlockStack>
  );
}
