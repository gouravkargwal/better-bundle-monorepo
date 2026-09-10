import {
  Badge,
  BlockStack,
  Box,
  Button,
  Card,
  InlineGrid,
  InlineStack,
  Text,
} from "@shopify/polaris";

interface ExtensionSetupGuideProps {
  shopDomain: string;
}

interface SetupSection {
  title: string;
  badge?: { text: string; tone: "attention" | "info" };
  description: string;
  steps: { step: string; text: string }[];
  blocks?: { icon: string; name: string; description: string }[];
  buttonLabel: string;
  buttonUrl: string;
}

export function ExtensionSetupGuide({
  shopDomain,
}: ExtensionSetupGuideProps) {
  const themeEditorUrl = `https://${shopDomain}/admin/themes/current/editor`;
  const checkoutSettingsUrl = `https://${shopDomain}/admin/settings/checkout`;

  const sections: SetupSection[] = [
    {
      title: "Storefront Recommendations",
      badge: { text: "Theme Editor", tone: "info" },
      description:
        "Add AI-powered recommendation widgets to your store pages. Each block shows personalized product suggestions to your customers.",
      steps: [
        { step: "1", text: "Go to Online Store > Themes > Customize" },
        {
          step: "2",
          text: "Navigate to the page you want (Homepage, Product, Collection, or Cart)",
        },
        {
          step: "3",
          text: 'Click "Add section" and search for "BetterBundle"',
        },
        {
          step: "4",
          text: "Customize the block settings (colors, product count, layout) and Save",
        },
      ],
      blocks: [
        {
          icon: "\uD83C\uDFE0",
          name: "Homepage",
          description:
            "Featured recommendations to help customers discover products",
        },
        {
          icon: "\uD83D\uDCE6",
          name: "Product Page",
          description:
            "Related products and frequently bought together suggestions",
        },
        {
          icon: "\uD83D\uDCC2",
          name: "Collection Page",
          description:
            "Recommendations relevant to the collection being browsed",
        },
        {
          icon: "\uD83D\uDED2",
          name: "Cart Page",
          description: "Add-on product suggestions to increase order value",
        },
      ],
      buttonLabel: "Open Theme Editor",
      buttonUrl: themeEditorUrl,
    },
    {
      title: "Checkout Recommendations",
      badge: { text: "Theme Editor", tone: "info" },
      description:
        "Show product recommendations on the checkout page. Customers can add suggested products to their cart before completing purchase.",
      steps: [
        { step: "1", text: "Go to Online Store > Themes > Customize" },
        { step: "2", text: "Navigate to the Checkout page" },
        {
          step: "3",
          text: 'Click "Add block" and select BetterBundle',
        },
        {
          step: "4",
          text: "Position the block where you want it and Save",
        },
      ],
      buttonLabel: "Open Theme Editor",
      buttonUrl: themeEditorUrl,
    },
    {
      title: "Customer Account Recommendations",
      badge: { text: "Theme Editor", tone: "info" },
      description:
        "Display personalized recommendations on customer account pages — order status, order history, and profile pages.",
      steps: [
        { step: "1", text: "Go to Online Store > Themes > Customize" },
        {
          step: "2",
          text: "Switch to a customer account page (Order status, Order index, or Profile)",
        },
        {
          step: "3",
          text: 'Click "Add block" and select BetterBundle',
        },
        { step: "4", text: "Position the block and Save" },
      ],
      buttonLabel: "Open Theme Editor",
      buttonUrl: themeEditorUrl,
    },
    {
      title: "Post-Purchase Upsells",
      badge: { text: "Checkout Settings", tone: "attention" },
      description:
        "Show one-click upsell offers after a customer completes their purchase. Customers can add products to their order without re-entering payment.",
      steps: [
        {
          step: "1",
          text: "Go to Settings > Checkout in your Shopify admin",
        },
        {
          step: "2",
          text: 'Scroll to the "Post-purchase page" section',
        },
        {
          step: "3",
          text: "Select BetterBundle as the post-purchase app",
        },
        { step: "4", text: "Save your checkout settings" },
      ],
      buttonLabel: "Open Checkout Settings",
      buttonUrl: checkoutSettingsUrl,
    },
  ];

  const renderSection = (section: SetupSection, compact = false) => (
    <div
      style={{
        transition: "all 0.2s ease-in-out",
        borderRadius: "8px",
        overflow: "hidden",
      }}
    >
      <Card>
        <div style={{ minHeight: compact ? "280px" : "auto", padding: "4px" }}>
          <BlockStack gap="300">
            <BlockStack gap="100">
              <InlineStack gap="200" blockAlign="center">
                <Text
                  as="h2"
                  variant={compact ? "headingSm" : "headingMd"}
                  fontWeight="bold"
                >
                  {section.title}
                </Text>
                {section.badge && (
                  <Badge tone={section.badge.tone} size="small">
                    {section.badge.text}
                  </Badge>
                )}
              </InlineStack>
              <Text as="p" variant="bodySm" tone="subdued">
                {section.description}
              </Text>
            </BlockStack>

            <Box
              padding={compact ? "300" : "400"}
              background="bg-surface-secondary"
              borderRadius="200"
            >
              <BlockStack gap={compact ? "200" : "300"}>
                {section.steps.map((item) => (
                  <InlineStack key={item.step} gap="200" blockAlign="center" wrap={false}>
                    <Badge>{String(item.step)}</Badge>
                    <Text as="p" variant="bodySm">
                      {item.text}
                    </Text>
                  </InlineStack>
                ))}
              </BlockStack>
            </Box>

            {section.blocks && (
              <InlineGrid columns={{ xs: 1, sm: 2 }} gap="300">
                {section.blocks.map((block) => (
                  <Box
                    key={block.name}
                    padding="300"
                    background="bg-surface-secondary"
                    borderRadius="200"
                  >
                    <InlineStack gap="200" blockAlign="center">
                      <span style={{ fontSize: "16px" }}>{block.icon}</span>
                      <BlockStack gap="050">
                        <Text
                          as="p"
                          variant="bodySm"
                          fontWeight="semibold"
                        >
                          {block.name}
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          {block.description}
                        </Text>
                      </BlockStack>
                    </InlineStack>
                  </Box>
                ))}
              </InlineGrid>
            )}

            <div>
              <Button
                variant="primary"
                size={compact ? "medium" : "large"}
                onClick={() => window.open(section.buttonUrl, "_blank")}
              >
                {section.buttonLabel}
              </Button>
            </div>
          </BlockStack>
        </div>
      </Card>
    </div>
  );

  return (
    <BlockStack gap="400">
      {/* Storefront — full width since it has sub-blocks */}
      {renderSection(sections[0])}

      {/* Checkout, Customer Account, Post-Purchase, Analytics — 2-column grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "16px",
          alignItems: "stretch",
        }}
      >
        {sections.slice(1).map((section) => renderSection(section, true))}

        {/* Analytics Pixel */}
        <div
          style={{
            borderRadius: "8px",
            overflow: "hidden",
          }}
        >
          <Card>
            <div style={{ padding: "4px" }}>
              <BlockStack gap="200">
                <InlineStack gap="200" blockAlign="center">
                  <Text as="h2" variant="headingSm" fontWeight="bold">
                    Analytics Pixel
                  </Text>
                  <Badge tone="success" size="small">
                    Auto-enabled
                  </Badge>
                </InlineStack>
                <Text as="p" variant="bodySm" tone="subdued">
                  Automatically tracks customer behavior across your store to
                  improve recommendation quality. Invisible to customers — no
                  setup required.
                </Text>
              </BlockStack>
            </div>
          </Card>
        </div>
      </div>
    </BlockStack>
  );
}
