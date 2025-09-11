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
        <Text as="h2" variant="headingMd">
          🚀 Installation Guide
        </Text>
        <Text as="p" variant="bodyMd" tone="subdued">
          Get your recommendations widget up and running
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

          <Button variant="primary" size="slim">
            Open Theme Editor
          </Button>
        </BlockStack>

        <Box background="bg-surface-brand" padding="300" borderRadius="200">
          <Text as="p" variant="bodySm" tone="subdued">
            💡 <strong>Pro Tip:</strong> The widget automatically adapts to each
            page type.
          </Text>
        </Box>
      </BlockStack>
    </Card>
  );
}
