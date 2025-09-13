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

export default reactExtension("customer-account.profile.block.render", () => (
  <ProfileWithRecommendations />
));

function ProfileWithRecommendations() {
  const { i18n } = useApi();
  const { id: customerId } = useAuthenticatedAccountCustomer();

  return (
    <BlockStack spacing="base">
      <Banner>
        <BlockStack inlineAlignment="center">
          <TextBlock>{i18n.translate("personalizedForYou")}</TextBlock>
        </BlockStack>
      </Banner>

      <Divider />

      {/* Product recommendations optimized for profile context */}
      <ProductRecommendations
        context="profile"
        title={i18n.translate("discoverNewFavorites")}
        limit={4}
        category="discovery"
        customerId={customerId}
      />
    </BlockStack>
  );
}
