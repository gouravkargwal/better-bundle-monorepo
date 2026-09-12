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
  apiKey?: string;
}

interface SetupSection {
  title: string;
  badge?: { text: string; tone: "attention" | "info" };
  description: string;
  steps: { step: string; text: string }[];
  blocks?: { icon: string; name: string; description: string; tag?: string }[];
  buttonLabel: string;
  buttonUrl: string;
}

export function ExtensionSetupGuide({
  shopDomain,
  apiKey,
}: ExtensionSetupGuideProps) {
  const themeEditorUrl = `https://${shopDomain}/admin/themes/current/editor`;
  const checkoutEditorUrl = `https://${shopDomain}/admin/settings/checkout/editor?page=checkout`;
  const accountsEditorUrl = `https://${shopDomain}/admin/settings/checkout/editor?page=order-status`;
  const checkoutSettingsUrl = `https://${shopDomain}/admin/settings/checkout#post-purchase-page`;

  // Shopify App Store compliance 5.1.3: deep-link directly into theme editor with block pre-selected
  const productThemeDeepLink = apiKey
    ? `https://${shopDomain}/admin/themes/current/editor?template=product&addAppBlockId=${apiKey}/Product-optimal&target=newAppsSection`
    : themeEditorUrl;

  const sections: SetupSection[] = [
    {
      title: "Storefront Recommendations",
      badge: { text: "Theme Editor", tone: "info" },
      description:
        "Add AI-powered recommendation widgets to your store pages. Each block shows personalized product suggestions to your customers.",
      steps: [
        {
          step: "1",
          text: 'Click "Add to Product Page" below to open the Theme Customizer with the BetterBundle section ready to place',
        },
        {
          step: "2",
          text: "Position the recommendation section where you want it on your product template",
        },
        {
          step: "3",
          text: "Customize the section styling (heading, colors, layout, product count) to match your store",
        },
        {
          step: "4",
          text: 'Click "Save" in the top right corner of the theme editor',
        },
      ],
      blocks: [
        {
          icon: "\uD83D\uDCE6",
          name: "Product Page",
          description:
            "Related products and frequently bought together suggestions",
        },
        {
          icon: "\uD83D\uDED2",
          name: "Cart Page",
          description: "Add-on product suggestions to increase order value",
          tag: "Coming soon",
        },
      ],
      buttonLabel: "Add to Product Page",
      buttonUrl: productThemeDeepLink,
    },
    {
      title: "Checkout Recommendations",
      badge: { text: "Checkout Editor", tone: "info" },
      description:
        "Show recommendations in checkout (Shopify Plus) and on Thank You pages (all Shopify plans).",
      steps: [
        {
          step: "1",
          text: 'Click "Open Checkout Editor" below to launch your checkout customizer',
        },
        {
          step: "2",
          text: 'In the sidebar, click "Add app block" and select "BetterBundle"',
        },
        {
          step: "3",
          text: "Position the recommendation block and click Save in top right",
        },
        {
          step: "4",
          text: "Switch to Thank-you page in top dropdown to add it there as well",
        },
      ],
      buttonLabel: "Open Checkout Editor",
      buttonUrl: checkoutEditorUrl,
    },
    {
      title: "Customer Account Recommendations",
      badge: { text: "Accounts Editor", tone: "info" },
      description:
        "Show recommendations on order status pages where buyers return to track delivery updates.",
      steps: [
        {
          step: "1",
          text: 'Click "Open Order Status Editor" below to launch accounts customizer',
        },
        {
          step: "2",
          text: 'In the sidebar, click "Add app block" and select "BetterBundle"',
        },
        {
          step: "3",
          text: "Position the block where you want it on order status page",
        },
        {
          step: "4",
          text: "Click Save in the top right corner to apply changes",
        },
      ],
      buttonLabel: "Open Order Status Editor",
      buttonUrl: accountsEditorUrl,
    },
    {
      title: "Post-Purchase Upsells",
      badge: { text: "Checkout Settings", tone: "attention" },
      description:
        "Show one-click upsell offers right after purchase without customers re-entering payment.",
      steps: [
        {
          step: "1",
          text: 'Click "Open Checkout Settings" below to open Shopify checkout settings',
        },
        {
          step: "2",
          text: 'Scroll down to the "Post-purchase page" section',
        },
        {
          step: "3",
          text: 'Select "BetterBundle" as your active post-purchase app',
        },
        {
          step: "4",
          text: "Click Save at the bottom of the checkout settings page",
        },
      ],
      buttonLabel: "Open Checkout Settings",
      buttonUrl: checkoutSettingsUrl,
    },
  ];

  const renderSection = (section: SetupSection, compact = false) => (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        transition: "all 0.2s ease-in-out",
        borderRadius: "8px",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          flex: 1,
          height: "100%",
        }}
        className="Polaris-Card-FullHeight"
      >
        <Card>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              height: "100%",
              flex: 1,
              padding: "4px",
            }}
          >
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
                <div style={{ minHeight: compact ? "36px" : "auto" }}>
                  <Text as="p" variant="bodySm" tone="subdued">
                    {section.description}
                  </Text>
                </div>
              </BlockStack>

              <Box
                padding={compact ? "300" : "400"}
                background="bg-surface-secondary"
                borderRadius="200"
                minHeight={compact ? "180px" : "auto"}
              >
                <BlockStack gap={compact ? "200" : "300"}>
                  {section.steps.map((item) => (
                    <InlineStack
                      key={item.step}
                      gap="200"
                      blockAlign="center"
                      wrap={false}
                    >
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
                          <InlineStack gap="150" blockAlign="center">
                            <Text as="p" variant="bodySm" fontWeight="semibold">
                              {block.name}
                            </Text>
                            {block.tag && (
                              <Badge tone="info" size="small">
                                {block.tag}
                              </Badge>
                            )}
                          </InlineStack>
                          <Text as="p" variant="bodySm" tone="subdued">
                            {block.description}
                          </Text>
                        </BlockStack>
                      </InlineStack>
                    </Box>
                  ))}
                </InlineGrid>
              )}
            </BlockStack>

            <div style={{ marginTop: "16px" }}>
              <Button
                variant="primary"
                size={compact ? "medium" : "large"}
                onClick={() => window.open(section.buttonUrl, "_blank")}
              >
                {section.buttonLabel}
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );

  return (
    <BlockStack gap="400">
      {/* Storefront — full width since it has sub-blocks */}
      {renderSection(sections[0])}

      {/* Checkout, Customer Account, Post-Purchase — 2-column grid */}
      <style>{`
        .Polaris-Card-FullHeight,
        .Polaris-Card-FullHeight > .Polaris-Card {
          height: 100% !important;
          display: flex !important;
          flex-direction: column !important;
          flex: 1 1 auto !important;
        }
        .Polaris-Card-FullHeight > .Polaris-Card > div {
          height: 100% !important;
          display: flex !important;
          flex-direction: column !important;
          flex: 1 1 auto !important;
        }
      `}</style>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "16px",
          alignItems: "stretch",
        }}
      >
        {sections.slice(1).map((section) => renderSection(section, true))}
      </div>
    </BlockStack>
  );
}
