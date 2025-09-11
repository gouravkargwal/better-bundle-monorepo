import {
  Card,
  BlockStack,
  Text,
  Button,
  Banner,
  InlineStack,
  InlineGrid,
  Badge,
} from "@shopify/polaris";
import { Form } from "@remix-run/react";
import { useState, useCallback, useEffect } from "react";

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
  // Initialize form state with config data (database defaults are already applied)
  const [formState, setFormState] = useState({
    // Only track the fields that users can actually configure
    productPageEnabled: config?.productPageEnabled ?? true,
    cartPageEnabled: config?.cartPageEnabled ?? true,
    homepageEnabled: config?.homepageEnabled ?? false,
    collectionPageEnabled: config?.collectionPageEnabled ?? true,
  });

  // Auto-dismiss success messages after 5 seconds
  const [showSuccessMessage, setShowSuccessMessage] = useState(false);

  useEffect(() => {
    if (actionData?.success) {
      setShowSuccessMessage(true);
      const timer = setTimeout(() => {
        setShowSuccessMessage(false);
      }, 5000); // Auto-dismiss after 5 seconds

      return () => clearTimeout(timer);
    }
  }, [actionData?.success]);

  const handleFormChange = useCallback((key: string, value: any) => {
    setFormState((prev: any) => ({ ...prev, [key]: value }));
  }, []);

  // Page configurations - AI model will determine optimal number of recommendations
  const pageConfigs = [
    {
      key: "product_page",
      label: "Product Pages",
      description: "Show related products to increase cross-selling",
      title: config?.productPageTitle || "You might also like",
      enabled: formState.productPageEnabled,
      icon: "🛍️",
    },
    {
      key: "cart_page",
      label: "Cart Page",
      description: "Suggest additional items to boost order value",
      title: config?.cartPageTitle || "Frequently bought together",
      enabled: formState.cartPageEnabled,
      icon: "🛒",
    },
    {
      key: "homepage",
      label: "Homepage",
      description: "Display popular products to new visitors",
      title: config?.homepageTitle || "Popular products",
      enabled: formState.homepageEnabled,
      icon: "🏠",
    },
    {
      key: "collection",
      label: "Collection Pages",
      description: "Show similar products within collections",
      title: config?.collectionPageTitle || "Similar products",
      enabled: formState.collectionPageEnabled,
      icon: "📦",
    },
  ];

  return (
    <Form method="post">
      <input type="hidden" name="id" value={config.id} />
      <input type="hidden" name="_action" value="update" />
      <input type="hidden" name="shop_id" value={config.shopId} />
      <input type="hidden" name="shop_domain" value={config.shopDomain} />

      {/* Only send the fields that users can actually configure */}
      <input
        type="hidden"
        name="productPageEnabled"
        value={formState.productPageEnabled}
      />
      <input
        type="hidden"
        name="cartPageEnabled"
        value={formState.cartPageEnabled}
      />
      <input
        type="hidden"
        name="homepageEnabled"
        value={formState.homepageEnabled}
      />
      <input
        type="hidden"
        name="collectionPageEnabled"
        value={formState.collectionPageEnabled}
      />

      <BlockStack gap="600">
        {/* Status Messages */}
        {actionData?.success && showSuccessMessage && (
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
                    case "product_page":
                      return "productPageEnabled";
                    case "cart_page":
                      return "cartPageEnabled";
                    case "homepage":
                      return "homepageEnabled";
                    case "collection":
                      return "collectionPageEnabled";
                    default:
                      return `${key}Enabled`;
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
              onClick={() => {
                setFormState({
                  // Reset only the fields that users can actually configure
                  productPageEnabled: config?.productPageEnabled ?? true,
                  cartPageEnabled: config?.cartPageEnabled ?? true,
                  homepageEnabled: config?.homepageEnabled ?? false,
                  collectionPageEnabled: config?.collectionPageEnabled ?? true,
                });
              }}
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
