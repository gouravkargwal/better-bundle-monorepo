import {
  Card,
  BlockStack,
  Text,
  Button,
  InlineStack,
  Box,
  Badge,
  List,
} from "@shopify/polaris";

export function WidgetInstallationSection() {
  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack align="space-between">
          <Text as="h2" variant="headingMd">
            🚀 Installation Guide
          </Text>
          <Badge tone="info" size="small">
            Step-by-step
          </Badge>
        </InlineStack>

        <Text as="p" variant="bodyMd" tone="subdued">
          Get your recommendations widget up and running in your Shopify theme
        </Text>

        <BlockStack gap="300">
          <InlineStack align="space-between">
            <Text as="h3" variant="headingSm">
              🎨 Theme Editor (Recommended)
            </Text>
            <Badge tone="success" size="small">
              Easy
            </Badge>
          </InlineStack>

          <Text as="p" variant="bodyMd" tone="subdued">
            Use Shopify's theme editor for a no-code setup
          </Text>

          <List type="number">
            <List.Item>
              Go to <strong>Online Store → Themes</strong>
            </List.Item>
            <List.Item>
              Click <strong>"Customize"</strong> on your active theme
            </List.Item>
            <List.Item>
              Navigate to the page where you want recommendations
            </List.Item>
            <List.Item>
              Click <strong>"Add section"</strong> →{" "}
              <strong>"Star Rating & Recommendations"</strong>
            </List.Item>
            <List.Item>Configure settings and save</List.Item>
          </List>

          <Button variant="primary" size="slim" url="/admin/themes" external>
            Open Theme Editor
          </Button>
        </BlockStack>

        <Box background="bg-surface-brand" padding="300" borderRadius="200">
          <Text as="p" variant="bodySm" tone="subdued">
            💡 <strong>Pro Tip:</strong> The widget automatically adapts to each
            page type and shows relevant recommendations based on your
            configuration.
          </Text>
        </Box>
      </BlockStack>
    </Card>
  );
}
