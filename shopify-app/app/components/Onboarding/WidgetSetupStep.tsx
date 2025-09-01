import { BlockStack, Text } from "@shopify/polaris";
import Widget from "../Widget/Widget";

export default function WidgetSetupStep() {
  return (
    <BlockStack gap="500" align="center">
      <Text as="h2" variant="headingLg">
        🎯 Setup Your Bundle Widget
      </Text>
      <Text as="p" variant="bodyMd" alignment="center">
        Now let's configure your widget to start collecting customer data and
        showing bundle recommendations.
      </Text>
      <Widget />
    </BlockStack>
  );
}
