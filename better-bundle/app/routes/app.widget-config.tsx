import {
  json,
  type ActionFunctionArgs,
  type LoaderFunctionArgs,
} from "@remix-run/node";
import { useLoaderData, useActionData, useNavigation } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import {
  getWidgetConfiguration,
  createDefaultConfiguration,
  updateWidgetConfiguration,
} from "../services/widget-config.service";
import { Page, Layout, InlineGrid, BlockStack } from "@shopify/polaris";
import { WidgetConfigForm } from "../components/Widget/WidgetConfigSection";
import { WidgetPreviewSection } from "../components/Widget/WidgetPreviewSection";
import { WidgetInstallationSection } from "../components/Widget/WidgetInstallationSection";
import { ExtensionStatusSection } from "../components/Widget/ExtensionStatusSection";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  console.log("🔧 Widget config loader - shop:", session.shop);

  // Get widget configuration (create default if doesn't exist)
  let config = await getWidgetConfiguration(session.shop);
  console.log("📋 Existing config found:", !!config);

  if (!config) {
    console.log("⚙️ Creating default configuration for:", session.shop);
    try {
      config = await createDefaultConfiguration(session.shop);
      console.log("✅ Default configuration created successfully");
    } catch (error) {
      console.error("❌ Error creating default configuration:", error);
      throw error;
    }
  }

  return json({
    config,
    shopDomain: session.shop,
  });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    const formData = await request.formData();
    const action = formData.get("_action") as string;

    console.log("🔧 Widget config action called:", action);
    console.log("📋 Form data keys:", Array.from(formData.keys()));

    if (action === "update") {
      // Process directly instead of forwarding
      const updateData: any = {};

      // Check if each field exists in form data before adding to updateData
      if (formData.has("productPageEnabled")) {
        updateData.productPageEnabled =
          formData.get("productPageEnabled") === "true";
      }
      if (formData.has("cartPageEnabled")) {
        updateData.cartPageEnabled = formData.get("cartPageEnabled") === "true";
      }
      if (formData.has("homepageEnabled")) {
        updateData.homepageEnabled = formData.get("homepageEnabled") === "true";
      }
      if (formData.has("collectionPageEnabled")) {
        updateData.collectionPageEnabled =
          formData.get("collectionPageEnabled") === "true";
      }

      console.log("📝 Update data:", updateData);

      const updatedConfig = await updateWidgetConfiguration(
        session.shop,
        updateData,
      );

      console.log("✅ Configuration updated successfully");

      return json({
        success: true,
        config: updatedConfig,
        message: "Widget configuration updated successfully",
      });
    }

    return json({ success: false, error: "Invalid action" });
  } catch (error) {
    console.error("Error in widget config action:", error);
    return json({
      success: false,
      error: error instanceof Error ? error.message : "Unknown error occurred",
    });
  }
};

export default function WidgetConfig() {
  const { config, shopDomain } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const navigation = useNavigation();
  const isSubmitting = navigation.state === "submitting";

  // Page configurations for preview
  const pageConfigs = [
    {
      key: "product_page",
      label: "Product Pages",
      title: config.productPageTitle || "You might also like",
    },
    {
      key: "cart_page",
      label: "Cart Page",
      title: config.cartPageTitle || "Frequently bought together",
    },
    {
      key: "homepage",
      label: "Homepage",
      title: config.homepageTitle || "Popular products",
    },
    {
      key: "collection",
      label: "Collection Pages",
      title: config.collectionPageTitle || "Similar products",
    },
  ];

  return (
    <Page>
      <Layout>
        <Layout.Section>
          <BlockStack gap="500">
            {/* Main Content Grid */}
            <InlineGrid columns={{ xs: 1, md: 2 }} gap="600">
              {/* Left Column - Configuration Form */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  height: "100%",
                }}
              >
                <WidgetConfigForm
                  config={config}
                  actionData={actionData || {}}
                  isSubmitting={isSubmitting}
                />
              </div>

              {/* Right Column - Preview & Installation */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  height: "100%",
                }}
              >
                <BlockStack gap="500">
                  <ExtensionStatusSection config={config} />
                  <WidgetPreviewSection
                    selectedPageType=""
                    pageConfigs={pageConfigs}
                    shopDomain={shopDomain}
                  />
                  <WidgetInstallationSection shopDomain={shopDomain} />
                </BlockStack>
              </div>
            </InlineGrid>
          </BlockStack>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
