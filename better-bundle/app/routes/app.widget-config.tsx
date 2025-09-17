import {
  json,
  type ActionFunctionArgs,
  type LoaderFunctionArgs,
} from "@remix-run/node";
import { useLoaderData, useFetcher } from "@remix-run/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { authenticate } from "../shopify.server";
import {
  getWidgetConfiguration,
  createDefaultConfiguration,
  updateWidgetConfiguration,
} from "../services/widget-config.service";
import {
  getExtensionStatus,
  installExtension,
} from "../services/extension.service";
import {
  Page,
  Layout,
  BlockStack,
  Card,
  Text,
  Button,
  InlineStack,
  Badge,
  InlineGrid,
  Divider,
  Banner,
} from "@shopify/polaris";
import { ExtensionManager } from "../components/Extensions/ExtensionManager";
import {
  openThemeEditorForPreview,
  openThemeEditorForInstall,
} from "../utils/theme-editor";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  // Get widget configuration (create default if doesn't exist)
  let config = await getWidgetConfiguration(session.shop);

  if (!config) {
    try {
      config = await createDefaultConfiguration(session.shop);
    } catch (error) {
      console.error("❌ Error creating default configuration:", error);
      throw error;
    }
  }

  // Get real extension status
  const extensionStatus = await getExtensionStatus(session.shop);

  return json({
    config,
    shopDomain: session.shop,
    extensionStatus,
  });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    const formData = await request.formData();
    const action = formData.get("_action") as string;

    if (action === "install_extension") {
      const extensionType = formData.get("extensionType") as string;
      const result = await installExtension(session.shop, extensionType);

      return json({
        success: result.success,
        message: result.message,
      });
    } else if (action === "auto_update_config") {
      // Handle auto-update from extension status detection
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

      const updatedConfig = await updateWidgetConfiguration(
        session.shop,
        updateData,
      );

      return json({
        success: true,
        config: updatedConfig,
        message: "Widget configuration auto-updated successfully",
      });
    } else if (action === "update") {
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

      const updatedConfig = await updateWidgetConfiguration(
        session.shop,
        updateData,
      );

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
  const { config, shopDomain, extensionStatus } =
    useLoaderData<typeof loader>();
  const fetcher = useFetcher<typeof action>();

  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleInstallExtension = useCallback(
    async (extensionType: string) => {
      const formData = new FormData();
      formData.append("_action", "install_extension");
      formData.append("extensionType", extensionType);

      fetcher.submit(formData, { method: "POST" });
    },
    [fetcher],
  );

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    // Refresh the page to get updated extension status
    window.location.reload();
  }, []);

  // Show success/error messages
  useEffect(() => {
    if (fetcher.data?.success && fetcher.data.message) {
      // You could show a toast notification here
      console.log("Success:", fetcher.data.message);
    } else if (fetcher.data?.error) {
      console.error("Error:", fetcher.data.error);
    }
  }, [fetcher.data]);

  return (
    <Page>
      <Layout>
        <Layout.Section>
          <BlockStack gap="500">
            {/* Header */}
            <Card>
              <BlockStack gap="400">
                <InlineStack align="space-between" blockAlign="center">
                  <Text as="h2" variant="headingLg">
                    Extension Management
                  </Text>
                  <Button
                    variant="secondary"
                    size="slim"
                    onClick={handleRefresh}
                    loading={isRefreshing || fetcher.state === "submitting"}
                    disabled={isRefreshing || fetcher.state === "submitting"}
                  >
                    Refresh Status
                  </Button>
                </InlineStack>

                <Text as="p" variant="bodyMd" tone="subdued">
                  Manage your BetterBundle extensions and track their
                  performance across your store.
                </Text>

                {fetcher.data?.message && (
                  <Banner tone={fetcher.data.success ? "success" : "critical"}>
                    {fetcher.data.message}
                  </Banner>
                )}
              </BlockStack>
            </Card>

            {/* Extension Manager */}
            <ExtensionManager
              extensionStatus={extensionStatus}
              onInstallExtension={handleInstallExtension}
              onRefresh={handleRefresh}
              isLoading={isRefreshing || fetcher.state === "submitting"}
            />

            {/* Theme Integration Help */}
            <Card>
              <BlockStack gap="400">
                <Text as="h3" variant="headingMd">
                  Theme Integration
                </Text>
                <Text as="p" variant="bodyMd">
                  Some extensions require manual theme integration. Use the
                  buttons below to open the theme editor and add widgets to your
                  pages.
                </Text>

                <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
                  <Button
                    variant="secondary"
                    size="large"
                    onClick={() => {
                      if (shopDomain) {
                        openThemeEditorForPreview(shopDomain);
                      }
                    }}
                    disabled={!shopDomain}
                    fullWidth
                  >
                    Preview Theme
                  </Button>

                  <Button
                    variant="primary"
                    size="large"
                    onClick={() => {
                      if (shopDomain) {
                        openThemeEditorForInstall(shopDomain, "product");
                      }
                    }}
                    disabled={!shopDomain}
                    fullWidth
                  >
                    Edit Theme
                  </Button>
                </InlineGrid>
              </BlockStack>
            </Card>
          </BlockStack>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
