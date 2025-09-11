import {
  Card,
  BlockStack,
  Text,
  Checkbox,
  Button,
  Banner,
  InlineStack,
  InlineGrid,
  Badge,
} from "@shopify/polaris";
import { Form } from "@remix-run/react";
import { useState, useCallback } from "react";

interface WidgetConfigFormProps {
  config: any; // Using any to handle the dynamic config structure
  actionData: { success?: boolean; message?: string; error?: string };
  isSubmitting: boolean;
}

export function WidgetConfigForm({
  config,
  actionData,
  isSubmitting,
}: WidgetConfigFormProps) {
  const [formState, setFormState] = useState(config);
  const [selectedPageType, setSelectedPageType] = useState<string>("");
  const [previewModal, setPreviewModal] = useState<{
    open: boolean;
    pageType: string;
  }>({
    open: false,
    pageType: "",
  });

  const handleFormChange = useCallback((key: string, value: any) => {
    setFormState((prev: any) => ({ ...prev, [key]: value }));
  }, []);

  // Page configurations - AI model will determine optimal number of recommendations
  const pageConfigs = [
    {
      key: "product_page",
      label: "Product Pages",
      description: "Show related products to increase cross-selling",
      title: formState.product_page_title || "You might also like",
      enabled: formState.product_page_enabled,
      icon: "🛍️",
    },
    {
      key: "cart_page",
      label: "Cart Page",
      description: "Suggest additional items to boost order value",
      title: formState.cart_page_title || "Frequently bought together",
      enabled: formState.cart_page_enabled,
      icon: "🛒",
    },
    {
      key: "homepage",
      label: "Homepage",
      description: "Display popular products to new visitors",
      title: formState.homepage_title || "Popular products",
      enabled: formState.homepage_enabled,
      icon: "🏠",
    },
    {
      key: "collection",
      label: "Collection Pages",
      description: "Show similar products within collections",
      title: formState.collection_page_title || "Similar products",
      enabled: formState.collection_page_enabled,
      icon: "📦",
    },
  ];

  return (
    <Form method="post">
      <input type="hidden" name="id" value={config.id} />
      <input type="hidden" name="_action" value="update" />
      <input type="hidden" name="shop_id" value={config.shop_id} />
      <input type="hidden" name="shop_domain" value={config.shop_domain} />

      <BlockStack gap="600">
        {/* Status Messages */}
        {actionData?.success && (
          <Banner tone="success">
            <p>{actionData.message || "Configuration saved successfully!"}</p>
          </Banner>
        )}
        {actionData?.error && (
          <Banner tone="critical">
            <p>Error: {actionData.error}</p>
          </Banner>
        )}

        {/* Main Header */}
        <Card>
          <BlockStack gap="300">
            <BlockStack gap="100">
              <Text as="h1" variant="headingLg">
                🎯 Smart Recommendations
              </Text>
              <Text as="p" variant="bodyMd" tone="subdued">
                Boost sales with AI-powered product recommendations across your
                store
              </Text>
            </BlockStack>
          </BlockStack>
        </Card>

        {/* Page Configuration */}
        <Card>
          <BlockStack gap="400">
            <BlockStack gap="100">
              <Text as="h2" variant="headingMd">
                📍 Where to Show Recommendations
              </Text>
              <Text as="p" variant="bodyMd" tone="subdued">
                Click on any page to enable/disable recommendations
              </Text>
            </BlockStack>

            <InlineGrid columns={{ xs: 1, sm: 2 }} gap="300">
              {pageConfigs.map((page) => {
                // Map the page key to the correct form field name
                const getFormFieldName = (key: string) => {
                  switch (key) {
                    case "collection":
                      return "collection_page_enabled";
                    default:
                      return `${key}_enabled`;
                  }
                };

                return (
                  <div
                    key={page.key}
                    style={{
                      cursor: "pointer",
                      border: "2px solid transparent",
                      transition: "all 0.2s ease",
                      minHeight: "120px", // Fixed height to prevent layout shift
                      padding: "12px",
                      backgroundColor: page.enabled ? "#f0f8ff" : "#f6f6f7",
                      borderRadius: "12px",
                      transform: "translateY(0)",
                      boxShadow: "0 2px 4px rgba(0, 0, 0, 0.1)",
                    }}
                    onClick={() => {
                      setSelectedPageType(page.key);
                      handleFormChange(
                        getFormFieldName(page.key),
                        !page.enabled,
                      );
                    }}
                  >
                    <BlockStack gap="200">
                      <InlineStack align="space-between">
                        <Text as="span" variant="headingSm">
                          {page.icon} {page.label}
                        </Text>
                        {page.enabled && (
                          <Badge tone="success" size="small">
                            ✓
                          </Badge>
                        )}
                      </InlineStack>

                      <Text as="p" variant="bodySm" tone="subdued">
                        {page.description}
                      </Text>
                    </BlockStack>
                  </div>
                );
              })}
            </InlineGrid>
          </BlockStack>
        </Card>

        {/* Action Buttons */}
        <Card>
          <InlineStack align="end" gap="300">
            <Button
              variant="secondary"
              onClick={() => setFormState({ ...config })}
            >
              Reset to Defaults
            </Button>
            <Button submit variant="primary" loading={isSubmitting}>
              {isSubmitting ? "Saving..." : "Save Configuration"}
            </Button>
          </InlineStack>
        </Card>
      </BlockStack>
    </Form>
  );
}
