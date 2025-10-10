// features/overview/components/HelpSection.tsx
import { Card, Text, BlockStack, Button } from "@shopify/polaris";
import { BillIcon } from "@shopify/polaris-icons";

export function HelpSection() {
  return (
    <Card>
      <div style={{ padding: "20px" }}>
        <BlockStack gap="300">
          <div
            style={{
              padding: "20px",
              backgroundColor: "#F0F9FF",
              borderRadius: "12px",
              border: "1px solid #BAE6FD",
            }}
          >
            <div style={{ color: "#0C4A6E" }}>
              <Text as="h3" variant="headingMd" fontWeight="bold">
                💡 Need Help?
              </Text>
            </div>
            <div style={{ marginTop: "8px" }}>
              <Text as="p" variant="bodyMd" tone="subdued">
                Get started with our guides and support
              </Text>
            </div>
          </div>
          <BlockStack gap="200">
            <Button
              url="mailto:support@betterbundle.com"
              variant="tertiary"
              size="large"
              icon={BillIcon}
            >
              Contact Support
            </Button>
          </BlockStack>
        </BlockStack>
      </div>
    </Card>
  );
}
