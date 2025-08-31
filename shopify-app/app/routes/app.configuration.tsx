import type { LoaderFunctionArgs, ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/server-runtime";
import { redirect } from "@remix-run/node";
import { useLoaderData, useActionData, Form } from "@remix-run/react";
import {
  Page,
  Layout,
  Card,
  Button,
  Text,
  BlockStack,
  InlineStack,
  Select,
  TextField,
  Checkbox,
  Badge,
  Modal,
  Banner,
  ButtonGroup,
} from "@shopify/polaris";
import { useState, useCallback } from "react";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  // Get shop configuration
  const shop = await prisma.shop.findFirst({
    where: { shopDomain: session.shop },
  });

  // Get all bundle recommendations
  const bundles = await prisma.bundleAnalysisResult.findMany({
    where: { shopId: shop?.id },
    include: {
      productData: {
        where: { shopId: shop?.id },
      },
    },
    orderBy: [{ confidence: "desc" }, { lift: "desc" }],
  });

  // Get widget configuration
  const widgetConfig = await prisma.widgetConfiguration.findFirst({
    where: { shopId: shop?.id },
  });

  return json({
    shop,
    bundles,
    widgetConfig: widgetConfig || {
      isEnabled: false,
      theme: "auto",
      position: "product_page",
      title: "Frequently Bought Together",
      showImages: true,
      showIndividualButtons: true,
      showBundleTotal: true,
      enabledBundles: [],
      globalDiscount: 0,
    },
  });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { admin, session } = await authenticate.admin(request);
  const formData = await request.formData();
  const action = formData.get("action");

  const shop = await prisma.shop.findFirst({
    where: { shopDomain: session.shop },
  });

  if (action === "save_config") {
    const isEnabled = formData.get("isEnabled") === "true";
    const theme = formData.get("theme") as string;
    const position = formData.get("position") as string;
    const title = formData.get("title") as string;
    const showImages = formData.get("showImages") === "true";
    const showIndividualButtons =
      formData.get("showIndividualButtons") === "true";
    const showBundleTotal = formData.get("showBundleTotal") === "true";
    const globalDiscount =
      parseFloat(formData.get("globalDiscount") as string) || 0;

    await prisma.widgetConfiguration.upsert({
      where: { shopId: shop?.id },
      update: {
        isEnabled,
        theme,
        position,
        title,
        showImages,
        showIndividualButtons,
        showBundleTotal,
        globalDiscount,
      },
      create: {
        shopId: shop?.id!,
        isEnabled,
        theme,
        position,
        title,
        showImages,
        showIndividualButtons,
        showBundleTotal,
        globalDiscount,
      },
    });

    return json({
      success: true,
      message: "Configuration saved successfully!",
    });
  }

  if (action === "toggle_bundle") {
    const bundleId = formData.get("bundleId") as string;
    const isEnabled = formData.get("isEnabled") === "true";
    const discount = parseFloat(formData.get("discount") as string) || 0;

    await prisma.bundleAnalysisResult.update({
      where: { id: bundleId },
      data: {
        isActive: isEnabled,
        discount,
      },
    });

    return json({ success: true, message: "Bundle updated successfully!" });
  }

  if (action === "enable_scheduled_analysis") {
    // Call the scheduler API to enable scheduled analysis
    const response = await fetch(
      `${request.url.split("/app")[0]}/api/scheduler`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          action: "enable-scheduled-analysis",
        }),
      },
    );

    const result = await response.json();
    return json(result);
  }

  if (action === "disable_scheduled_analysis") {
    // Call the scheduler API to disable scheduled analysis
    const response = await fetch(
      `${request.url.split("/app")[0]}/api/scheduler`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          action: "disable-scheduled-analysis",
        }),
      },
    );

    const result = await response.json();
    return json(result);
  }

  return json({ success: false, message: "Invalid action" });
};

export default function ConfigurationPage() {
  const { shop, bundles, widgetConfig } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();

  const [activeModal, setActiveModal] = useState<string | null>(null);
  const [selectedBundle, setSelectedBundle] = useState<any>(null);
  const [previewTheme, setPreviewTheme] = useState(widgetConfig.theme);

  const handleBundleEdit = useCallback((bundle: any) => {
    setSelectedBundle(bundle);
    setActiveModal("bundle_edit");
  }, []);

  const handlePreviewTheme = useCallback((theme: string) => {
    setPreviewTheme(theme);
  }, []);

  const themeOptions = [
    { label: "Auto (Follow Theme)", value: "auto" },
    { label: "Light Mode", value: "light" },
    { label: "Dark Mode", value: "dark" },
    { label: "High Contrast", value: "high_contrast" },
  ];

  const positionOptions = [
    { label: "Product Page", value: "product_page" },
    { label: "Cart Page", value: "cart_page" },
    { label: "Both", value: "both" },
  ];

  return (
    <Page
      title="Widget Configuration"
      subtitle="Customize how bundle recommendations appear on your store"
    >
      <Layout>
        {actionData?.success && (
          <Layout.Section>
            <Banner status="success" title={actionData.message} />
          </Layout.Section>
        )}

        {/* Scheduled Analysis Control */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text variant="headingMd" as="h2">
                Scheduled Analysis Control
              </Text>

              <BlockStack gap="300">
                <Text as="p">
                  Enable scheduled analysis to automatically analyze your store
                  data based on heuristic timing and update bundle
                  recommendations.
                </Text>

                <InlineStack gap="300">
                  <Form method="post">
                    <input
                      type="hidden"
                      name="action"
                      value="enable_scheduled_analysis"
                    />
                    <Button submit variant="primary">
                      Enable Scheduled Analysis
                    </Button>
                  </Form>

                  <Form method="post">
                    <input
                      type="hidden"
                      name="action"
                      value="disable_scheduled_analysis"
                    />
                    <Button submit variant="secondary">
                      Disable Scheduled Analysis
                    </Button>
                  </Form>
                </InlineStack>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* General Settings */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text variant="headingMd" as="h2">
                General Settings
              </Text>

              <Form method="post">
                <input type="hidden" name="action" value="save_config" />

                <BlockStack gap="400">
                  <InlineStack align="space-between">
                    <Text variant="bodyMd" as="p">
                      Enable Bundle Recommendations
                    </Text>
                    <Checkbox
                      label=""
                      checked={widgetConfig.isEnabled}
                      onChange={(checked) => {
                        // Handle checkbox change
                      }}
                      name="isEnabled"
                      value={widgetConfig.isEnabled ? "true" : "false"}
                    />
                  </InlineStack>

                  <Select
                    label="Theme Mode"
                    options={themeOptions}
                    value={widgetConfig.theme}
                    onChange={handlePreviewTheme}
                    name="theme"
                    helpText="Choose how the widget adapts to your theme"
                  />

                  <Select
                    label="Display Position"
                    options={positionOptions}
                    value={widgetConfig.position}
                    name="position"
                    helpText="Where to show bundle recommendations"
                  />

                  <TextField
                    label="Widget Title"
                    value={widgetConfig.title}
                    name="title"
                    helpText="Title shown above bundle recommendations"
                  />

                  <InlineStack gap="400">
                    <Checkbox
                      label="Show Product Images"
                      checked={widgetConfig.showImages}
                      name="showImages"
                      value={widgetConfig.showImages ? "true" : "false"}
                    />
                    <Checkbox
                      label="Show Individual Add Buttons"
                      checked={widgetConfig.showIndividualButtons}
                      name="showIndividualButtons"
                      value={
                        widgetConfig.showIndividualButtons ? "true" : "false"
                      }
                    />
                    <Checkbox
                      label="Show Bundle Total"
                      checked={widgetConfig.showBundleTotal}
                      name="showBundleTotal"
                      value={widgetConfig.showBundleTotal ? "true" : "false"}
                    />
                  </InlineStack>

                  <TextField
                    label="Global Discount (%)"
                    type="number"
                    value={widgetConfig.globalDiscount.toString()}
                    name="globalDiscount"
                    helpText="Default discount applied to all bundles"
                    suffix="%"
                  />

                  <Button submit variant="primary">
                    Save Configuration
                  </Button>
                </BlockStack>
              </Form>
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Theme Preview */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text variant="headingMd" as="h2">
                Theme Preview
              </Text>

              <div
                style={{
                  padding: "1rem",
                  border: "1px solid #e1e5e9",
                  borderRadius: "8px",
                  backgroundColor:
                    previewTheme === "dark" ? "#1a1a1a" : "#ffffff",
                  color: previewTheme === "dark" ? "#ffffff" : "#202223",
                }}
              >
                <Text
                  variant="headingSm"
                  as="h3"
                  style={{ marginBottom: "1rem" }}
                >
                  {widgetConfig.title}
                </Text>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "1rem",
                    padding: "1rem",
                    border: "1px solid #e5e5e5",
                    borderRadius: "6px",
                    backgroundColor:
                      previewTheme === "dark" ? "#2a2a2a" : "#ffffff",
                  }}
                >
                  <div
                    style={{
                      width: "60px",
                      height: "60px",
                      backgroundColor: "#f9f9f9",
                      borderRadius: "4px",
                      border: "1px solid #e5e5e5",
                    }}
                  />

                  <div style={{ flex: 1 }}>
                    <Text
                      variant="bodyMd"
                      as="p"
                      style={{ marginBottom: "0.25rem" }}
                    >
                      Sample Product
                    </Text>
                    <Text variant="bodySm" as="p" style={{ color: "#6d7175" }}>
                      ₹299.00
                    </Text>
                  </div>

                  <Button size="slim" variant="primary">
                    Add to Cart
                  </Button>
                </div>

                <div
                  style={{
                    marginTop: "1rem",
                    padding: "1rem",
                    backgroundColor:
                      previewTheme === "dark" ? "#2a2a2a" : "#f9f9f9",
                    border: "1px solid #e5e5e5",
                    borderRadius: "6px",
                    textAlign: "center",
                  }}
                >
                  <Text
                    variant="bodyMd"
                    as="p"
                    style={{ marginBottom: "0.75rem" }}
                  >
                    Bundle Total: ₹499.00
                  </Text>
                  <Button size="large" variant="primary" fullWidth>
                    Add Both to Cart
                  </Button>
                </div>
              </div>
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Bundle Management */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text variant="headingMd" as="h2">
                Bundle Management
              </Text>

              <Text variant="bodyMd" as="p">
                Enable or disable specific bundles and set individual discounts
              </Text>

              <BlockStack gap="300">
                {bundles.map((bundle) => (
                  <div
                    key={bundle.id}
                    style={{
                      padding: "1rem",
                      border: "1px solid #e1e5e9",
                      borderRadius: "8px",
                      backgroundColor: bundle.isActive ? "#f1f8f5" : "#f6f6f7",
                    }}
                  >
                    <InlineStack align="space-between">
                      <BlockStack gap="200">
                        <InlineStack gap="200" align="baseline">
                          <Text variant="bodyMd" as="p" fontWeight="semibold">
                            Bundle #{bundle.id.slice(-6)}
                          </Text>
                          <Badge status={bundle.isActive ? "success" : "info"}>
                            {bundle.isActive ? "Active" : "Inactive"}
                          </Badge>
                        </InlineStack>

                        <Text variant="bodySm" as="p" tone="subdued">
                          Confidence: {(bundle.confidence * 100).toFixed(1)}% |
                          Lift: {bundle.lift.toFixed(2)}x | Purchased together:{" "}
                          {bundle.coPurchaseCount} times
                        </Text>

                        {bundle.discount > 0 && (
                          <Text variant="bodySm" as="p" tone="success">
                            Discount: {bundle.discount}% off
                          </Text>
                        )}
                      </BlockStack>

                      <ButtonGroup>
                        <Button
                          size="slim"
                          onClick={() => handleBundleEdit(bundle)}
                        >
                          Edit
                        </Button>
                      </ButtonGroup>
                    </InlineStack>
                  </div>
                ))}
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>

      {/* Bundle Edit Modal */}
      <Modal
        open={activeModal === "bundle_edit"}
        onClose={() => setActiveModal(null)}
        title="Edit Bundle"
        primaryAction={{
          content: "Save",
          onAction: () => {
            // Handle save
            setActiveModal(null);
          },
        }}
        secondaryActions={[
          {
            content: "Cancel",
            onAction: () => setActiveModal(null),
          },
        ]}
      >
        <Modal.Section>
          {selectedBundle && (
            <BlockStack gap="400">
              <Text variant="bodyMd" as="p">
                Bundle ID: {selectedBundle.id}
              </Text>

              <Checkbox
                label="Enable this bundle"
                checked={selectedBundle.isActive}
                helpText="Show this bundle to customers"
              />

              <TextField
                label="Bundle Discount (%)"
                type="number"
                value={selectedBundle.discount?.toString() || "0"}
                helpText="Discount applied when customers buy this bundle"
                suffix="%"
              />

              <Text variant="bodySm" as="p" tone="subdued">
                Products in this bundle: {selectedBundle.productIds.join(", ")}
              </Text>
            </BlockStack>
          )}
        </Modal.Section>
      </Modal>
    </Page>
  );
}
