import React, { useState } from "react";
import {
  Page,
  Layout,
  Card,
  FormLayout,
  TextField,
  Select,
  Checkbox,
  Button,
  BlockStack,
  InlineStack,
  Text,
  Banner,
  Badge,
  Divider,
  Box,
} from "@shopify/polaris";
import { useNavigate } from "@remix-run/react";

interface WidgetConfig {
  id?: string;
  isEnabled: boolean;
  theme: string;
  position: string;
  title: string;
  showImages: boolean;
  showIndividualButtons: boolean;
  showBundleTotal: boolean;
  globalDiscount: number;
}

interface WidgetProps {
  shop: {
    id: string;
    shopId: string;
    shopDomain: string;
  };
  initialConfig: WidgetConfig;
}

const THEME_OPTIONS = [
  { label: "Auto (Follows your theme)", value: "auto" },
  { label: "Light", value: "light" },
  { label: "Dark", value: "dark" },
  { label: "Minimal", value: "minimal" },
];

const POSITION_OPTIONS = [
  { label: "Product Page", value: "product_page" },
  { label: "Cart Page", value: "cart_page" },
  { label: "Collection Page", value: "collection_page" },
  { label: "Homepage", value: "homepage" },
];

export default function Widget({ shop, initialConfig }: WidgetProps) {
  const navigate = useNavigate();
  const [isSaving, setIsSaving] = useState(false);
  const [config, setConfig] = useState<WidgetConfig>(initialConfig);
  const [hasChanges, setHasChanges] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">(
    "idle",
  );

  const handleConfigChange = (key: keyof WidgetConfig, value: any) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus("idle");

    try {
      // For now, just simulate saving - you can implement actual API call later
      console.log("Saving widget config:", config);

      // Simulate API delay
      await new Promise((resolve) => setTimeout(resolve, 1000));

      setSaveStatus("success");
      setHasChanges(false);
      setTimeout(() => setSaveStatus("idle"), 3000);
    } catch (error) {
      console.error("Failed to save widget config:", error);
      setSaveStatus("error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setConfig({
      isEnabled: false,
      theme: "auto",
      position: "product_page",
      title: "Frequently Bought Together",
      showImages: true,
      showIndividualButtons: true,
      showBundleTotal: true,
      globalDiscount: 0,
    });
    setHasChanges(false);
  };

  const getWidgetPreview = () => {
    const previewStyle = {
      border: "1px solid #ddd",
      borderRadius: "8px",
      padding: "16px",
      margin: "16px 0",
      backgroundColor:
        config.theme === "dark"
          ? "#2c2c2c"
          : config.theme === "light"
            ? "#ffffff"
            : "#f6f6f7",
      color: config.theme === "dark" ? "#ffffff" : "#202223",
    };

    return (
      <Box padding="400" background="bg-surface-secondary" borderRadius="200">
        <Text as="h3" variant="headingMd">
          Widget Preview
        </Text>
        <div style={previewStyle}>
          <Text as="h4" variant="headingSm">
            {config.title}
          </Text>
          {config.showImages && (
            <div style={{ display: "flex", gap: "8px", margin: "12px 0" }}>
              <div
                style={{
                  width: "60px",
                  height: "60px",
                  backgroundColor: "#ddd",
                  borderRadius: "4px",
                }}
              />
              <div
                style={{
                  width: "60px",
                  height: "60px",
                  backgroundColor: "#ddd",
                  borderRadius: "4px",
                }}
              />
              <div
                style={{
                  width: "60px",
                  height: "60px",
                  backgroundColor: "#ddd",
                  borderRadius: "4px",
                }}
              />
            </div>
          )}
          <div style={{ display: "flex", gap: "8px", margin: "12px 0" }}>
            {config.showIndividualButtons && (
              <Button size="slim">Add to Cart</Button>
            )}
            {config.showBundleTotal && (
              <Button size="slim" variant="primary">
                Add Bundle (${(100 - config.globalDiscount).toFixed(2)})
              </Button>
            )}
          </div>
        </div>
      </Box>
    );
  };

  return (
    <Page
      title="Widget Configuration"
      backAction={{
        content: "Dashboard",
        onAction: () => navigate("/app/step/dashboard"),
      }}
      primaryAction={
        <Button
          variant="primary"
          onClick={handleSave}
          loading={isSaving}
          disabled={!hasChanges}
        >
          Save Configuration
        </Button>
      }
    >
      <Layout>
        <Layout.Section>
          <Card>
            <BlockStack gap="500">
              <Banner title="🎯 Configure Your Bundle Widget" tone="info">
                <p>
                  Customize how your bundle recommendations appear to customers.
                  These settings will affect the appearance and behavior of your
                  widget.
                </p>
              </Banner>

              {saveStatus === "success" && (
                <Banner tone="success">
                  Widget configuration saved successfully!
                </Banner>
              )}

              {saveStatus === "error" && (
                <Banner tone="critical">
                  Failed to save widget configuration. Please try again.
                </Banner>
              )}

              <FormLayout>
                <div
                  style={{ display: "flex", alignItems: "center", gap: "8px" }}
                >
                  <Checkbox
                    label="Enable Widget"
                    checked={config.isEnabled}
                    onChange={(checked) =>
                      handleConfigChange("isEnabled", checked)
                    }
                  />
                  <Badge tone={config.isEnabled ? "success" : "attention"}>
                    {config.isEnabled ? "Active" : "Inactive"}
                  </Badge>
                </div>

                <TextField
                  label="Widget Title"
                  value={config.title}
                  onChange={(value) => handleConfigChange("title", value)}
                  helpText="This will be displayed above your bundle recommendations"
                  autoComplete="off"
                />

                <Select
                  label="Theme"
                  options={THEME_OPTIONS}
                  value={config.theme}
                  onChange={(value) => handleConfigChange("theme", value)}
                  helpText="Choose how your widget looks"
                />

                <Select
                  label="Position"
                  options={POSITION_OPTIONS}
                  value={config.position}
                  onChange={(value) => handleConfigChange("position", value)}
                  helpText="Where to display the widget on your store"
                />

                <TextField
                  label="Global Discount (%)"
                  type="number"
                  value={config.globalDiscount.toString()}
                  onChange={(value) =>
                    handleConfigChange("globalDiscount", parseFloat(value) || 0)
                  }
                  helpText="Percentage discount applied to all bundles"
                  suffix="%"
                  autoComplete="off"
                />

                <Divider />

                <Text as="h3" variant="headingMd">
                  Display Options
                </Text>

                <Checkbox
                  label="Show Product Images"
                  checked={config.showImages}
                  onChange={(checked) =>
                    handleConfigChange("showImages", checked)
                  }
                  helpText="Display product images in bundle recommendations"
                />

                <Checkbox
                  label="Show Individual Add to Cart Buttons"
                  checked={config.showIndividualButtons}
                  onChange={(checked) =>
                    handleConfigChange("showIndividualButtons", checked)
                  }
                  helpText="Allow customers to add individual products to cart"
                />

                <Checkbox
                  label="Show Bundle Total"
                  checked={config.showBundleTotal}
                  onChange={(checked) =>
                    handleConfigChange("showBundleTotal", checked)
                  }
                  helpText="Display the total price for the entire bundle"
                />
              </FormLayout>

              {getWidgetPreview()}

              <InlineStack gap="300" align="center">
                <Button onClick={handleReset} disabled={!hasChanges}>
                  Reset to Defaults
                </Button>
                <Button
                  variant="primary"
                  onClick={handleSave}
                  loading={isSaving}
                  disabled={!hasChanges}
                >
                  Save Configuration
                </Button>
              </InlineStack>
            </BlockStack>
          </Card>
        </Layout.Section>

        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h3" variant="headingMd">
                💡 Tips
              </Text>
              <Text as="p" variant="bodyMd">
                • Enable the widget to start collecting customer data
              </Text>
              <Text as="p" variant="bodyMd">
                • Choose a theme that matches your store's design
              </Text>
              <Text as="p" variant="bodyMd">
                • Position the widget where customers will see it most
              </Text>
              <Text as="p" variant="bodyMd">
                • Use global discounts to encourage bundle purchases
              </Text>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
