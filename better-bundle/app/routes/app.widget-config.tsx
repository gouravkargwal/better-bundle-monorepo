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
} from "@shopify/polaris";

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

    if (action === "auto_update_config") {
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
  const { config, shopDomain } = useLoaderData<typeof loader>();
  const fetcher = useFetcher<typeof action>();

  const [extensionStatus, setExtensionStatus] = useState<any>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [, setCurrentConfig] = useState(config);
  const hasAutoUpdated = useRef(false);
  const configRef = useRef(config);
  const autoUpdateConfigRef = useRef<
    ((statusData: any) => Promise<void>) | null
  >(null);

  // Safeguards for repeated updates
  const lastUpdateTime = useRef<number>(0);
  const updateRetryCount = useRef<number>(0);
  const MAX_RETRIES = 3;
  const MIN_UPDATE_INTERVAL = 5000; // 5 seconds

  // Debouncing for fetchExtensionStatus
  const fetchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  // const DEBOUNCE_DELAY = 1000; // 1 second (for future use)

  // Update config ref and current config when config changes
  useEffect(() => {
    configRef.current = config;
    setCurrentConfig(config);
  }, [config]);

  // Handle fetcher response to update state without page reload
  useEffect(() => {
    if (
      fetcher.data?.success &&
      "config" in fetcher.data &&
      fetcher.data.config
    ) {
      setCurrentConfig(fetcher.data.config);
      configRef.current = fetcher.data.config;
      updateRetryCount.current = 0; // Reset retry count on successful update
    }
  }, [fetcher.data]);

  // Add CSS animation for skeleton loading
  useEffect(() => {
    const style = document.createElement("style");
    style.textContent = `
      @keyframes pulse {
        0%, 100% { opacity: 0.7; }
        50% { opacity: 0.4; }
      }
    `;
    document.head.appendChild(style);
    return () => {
      document.head.removeChild(style);
    };
  }, []);

  // Auto-detect installed pages from extension status
  const getInstalledPages = () => {
    if (!extensionStatus?.pageStatuses) return [];

    return extensionStatus.pageStatuses
      .filter((page: any) => page.isActive)
      .map((page: any) => {
        const displayNames: Record<string, string> = {
          product_page: "Product Pages",
          homepage: "Homepage",
          collection: "Collection Pages",
          cart_page: "Cart Page",
        };
        return displayNames[page.pageType] || page.pageType;
      });
  };

  const installedPages = getInstalledPages();

  // Auto-update config when extension status changes (via server action)
  const autoUpdateConfig = useCallback(
    async (statusData: any) => {
      if (!statusData?.pageStatuses) return;

      try {
        const updates: any = {};

        // Map detected installations to config fields
        statusData.pageStatuses.forEach((page: any) => {
          const isInstalled = page.isActive;

          switch (page.pageType) {
            case "product_page":
              updates.productPageEnabled = isInstalled;
              break;
            case "homepage":
              updates.homepageEnabled = isInstalled;
              break;
            case "collection":
              updates.collectionPageEnabled = isInstalled;
              break;
            case "cart_page":
              updates.cartPageEnabled = isInstalled;
              break;
          }
        });

        // Only update if there are changes
        const hasChanges = Object.keys(updates).some(
          (key) => (configRef.current as any)[key] !== updates[key],
        );

        if (hasChanges) {
          // Safeguard: Check if enough time has passed since last update
          const now = Date.now();
          const timeSinceLastUpdate = now - lastUpdateTime.current;

          if (timeSinceLastUpdate < MIN_UPDATE_INTERVAL) {
            console.error(
              `⏰ Skipping update - too soon since last update (${timeSinceLastUpdate}ms < ${MIN_UPDATE_INTERVAL}ms)`,
            );
            return;
          }

          // Safeguard: Check retry count
          if (updateRetryCount.current >= MAX_RETRIES) {
            console.error(
              `🚫 Max retries reached (${MAX_RETRIES}), skipping auto-update`,
            );
            return;
          }

          console.error(
            "🔄 Auto-updating config based on detected installations:",
            updates,
          );

          // Update timestamps and retry count
          lastUpdateTime.current = now;
          updateRetryCount.current += 1;

          // Use fetcher instead of direct fetch to avoid page reload
          const formData = new FormData();
          formData.append("_action", "auto_update_config");
          Object.entries(updates).forEach(([key, value]) => {
            formData.append(key, String(value));
          });

          fetcher.submit(formData, { method: "POST" });
        }
      } catch (error) {
        console.error("Error auto-updating config:", error);
        updateRetryCount.current += 1; // Increment retry count on error
      }
    },
    [fetcher], // Include fetcher dependency
  );

  // Store autoUpdateConfig in ref
  useEffect(() => {
    autoUpdateConfigRef.current = autoUpdateConfig;
  }, [autoUpdateConfig]);

  // Immediate fetch function for manual refresh
  const fetchExtensionStatus = useCallback(async () => {
    // Clear any pending debounced calls
    if (fetchTimeoutRef.current) {
      clearTimeout(fetchTimeoutRef.current);
    }

    setIsRefreshing(true);
    setCheckError(null); // Clear previous errors
    try {
      const response = await fetch("/app/api/extension-status");
      const data = await response.json();

      if (data.success) {
        setExtensionStatus(data.status);
        setCheckError(null); // Clear any previous errors
        // Auto-update config after fetching status - but only once
        if (!hasAutoUpdated.current && autoUpdateConfigRef.current) {
          hasAutoUpdated.current = true;
          setTimeout(() => {
            autoUpdateConfigRef.current?.(data.status);
          }, 100);
        }
      } else {
        // API returned an error
        setCheckError(data.error || "Failed to check extension status");
        setExtensionStatus(null);
      }
    } catch (error) {
      console.error("Error fetching extension status:", error);
      setCheckError("Network error: Unable to check extension status");
      setExtensionStatus(null);
    } finally {
      setIsRefreshing(false);
    }
  }, []); // Remove autoUpdateConfig dependency to prevent infinite loop

  // Fetch status on mount
  useEffect(() => {
    fetchExtensionStatus();
  }, [fetchExtensionStatus]);

  // Cleanup timeout on unmount
  useEffect(() => {
    const timeoutRef = fetchTimeoutRef.current;
    return () => {
      if (timeoutRef) {
        clearTimeout(timeoutRef);
      }
    };
  }, []);

  return (
    <Page>
      <Layout>
        <Layout.Section>
          <BlockStack gap="500">
            {/* Header */}
            <Card>
              <BlockStack gap="400">
                <InlineStack align="space-between" blockAlign="center">
                  <Text as="h2" variant="headingMd">
                    Widget Management
                  </Text>
                  <Button
                    variant="secondary"
                    size="slim"
                    onClick={fetchExtensionStatus}
                    loading={isRefreshing || fetcher.state === "submitting"}
                    disabled={isRefreshing || fetcher.state === "submitting"}
                    icon="refresh"
                  >
                    Refresh
                  </Button>
                </InlineStack>

                <Text as="p" variant="bodySm" tone="subdued">
                  {isRefreshing
                    ? "Checking widget installation status..."
                    : fetcher.state === "submitting"
                      ? "Updating configuration..."
                      : checkError
                        ? `Error: ${checkError}`
                        : extensionStatus
                          ? installedPages.length > 0
                            ? `Widget is active on: ${installedPages.join(", ")}`
                            : "Widget not installed yet"
                          : "Click 'Refresh Status' to check installation status"}
                </Text>
              </BlockStack>
            </Card>

            {/* Main Status Display */}
            <InlineGrid columns={{ xs: 1, md: 2 }} gap="600">
              {/* Left Column - Installation Status */}
              <Card>
                <BlockStack gap="400">
                  <Text as="h3" variant="headingMd">
                    Installation Status
                  </Text>
                  {isRefreshing ? (
                    <BlockStack gap="400">
                      {[
                        "Product Pages",
                        "Homepage",
                        "Collection Pages",
                        "Cart Page",
                      ].map((pageName) => (
                        <InlineStack
                          key={pageName}
                          align="space-between"
                          blockAlign="center"
                          gap="400"
                        >
                          <div
                            style={{
                              width: "120px",
                              height: "20px",
                              backgroundColor: "#f0f0f0",
                              borderRadius: "4px",
                              animation: "pulse 1.5s ease-in-out infinite",
                            }}
                          />
                          <div
                            style={{
                              width: "80px",
                              height: "24px",
                              backgroundColor: "#f0f0f0",
                              borderRadius: "12px",
                              animation: "pulse 1.5s ease-in-out infinite",
                            }}
                          />
                        </InlineStack>
                      ))}
                    </BlockStack>
                  ) : checkError ? (
                    <BlockStack gap="400">
                      <InlineStack
                        align="space-between"
                        blockAlign="center"
                        gap="400"
                      >
                        <Text as="p" variant="bodyMd" tone="critical">
                          Status Check Failed
                        </Text>
                        <Badge tone="critical">Error</Badge>
                      </InlineStack>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {checkError}
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        You can still manually add the widget to your theme
                        pages using the buttons below.
                      </Text>
                      <Button
                        variant="tertiary"
                        size="slim"
                        onClick={fetchExtensionStatus}
                        loading={isRefreshing}
                        disabled={isRefreshing}
                      >
                        Retry Check
                      </Button>
                    </BlockStack>
                  ) : extensionStatus ? (
                    <BlockStack gap="400">
                      {extensionStatus.pageStatuses?.map((page: any) => (
                        <InlineStack
                          key={page.pageType}
                          align="space-between"
                          blockAlign="center"
                          gap="400"
                        >
                          <Text as="p" variant="bodyMd">
                            {page.pageType === "product_page" &&
                              "Product Pages"}
                            {page.pageType === "homepage" && "Homepage"}
                            {page.pageType === "collection" &&
                              "Collection Pages"}
                            {page.pageType === "cart_page" && "Cart Page"}
                          </Text>
                          <Badge tone={page.isActive ? "success" : "critical"}>
                            {page.isActive ? "Active" : "Not Installed"}
                          </Badge>
                        </InlineStack>
                      ))}
                    </BlockStack>
                  ) : (
                    <Text as="p" variant="bodyMd" tone="subdued">
                      Click 'Refresh Status' to check where your widget is
                      installed.
                    </Text>
                  )}
                </BlockStack>
              </Card>

              {/* Right Column - Page Management */}
              <Card>
                <BlockStack gap="400">
                  <Text as="h3" variant="headingMd">
                    Page Management
                  </Text>
                  {checkError && (
                    <Text as="p" variant="bodySm" tone="subdued">
                      Since the status check failed, you can manually add the
                      widget to any page below.
                    </Text>
                  )}
                  <BlockStack gap="300">
                    {[
                      {
                        type: "product_page",
                        label: "Product Pages",
                        template: "product",
                      },
                      {
                        type: "homepage",
                        label: "Homepage",
                        template: "index",
                      },
                      {
                        type: "collection",
                        label: "Collection Pages",
                        template: "collection",
                      },
                      {
                        type: "cart_page",
                        label: "Cart Page",
                        template: "cart",
                      },
                    ].map((page) => {
                      const isActive =
                        extensionStatus?.pageStatuses?.find(
                          (p: any) => p.pageType === page.type,
                        )?.isActive || false;

                      return (
                        <InlineStack
                          key={page.type}
                          align="space-between"
                          blockAlign="center"
                        >
                          <Text as="p" variant="bodyMd">
                            {page.label}
                          </Text>
                          <Button
                            variant={isActive ? "secondary" : "primary"}
                            size="slim"
                            onClick={() => {
                              if (shopDomain) {
                                if (isActive) {
                                  // For removal, we'll open theme editor to the specific page
                                  // where they can manually remove the block
                                  openThemeEditorForInstall(
                                    shopDomain,
                                    page.template,
                                  );
                                } else {
                                  // For addition, open theme editor to add the block
                                  openThemeEditorForInstall(
                                    shopDomain,
                                    page.template,
                                  );
                                }
                              }
                            }}
                            disabled={
                              !shopDomain ||
                              isRefreshing ||
                              fetcher.state === "submitting"
                            }
                            loading={
                              isRefreshing || fetcher.state === "submitting"
                            }
                          >
                            {checkError
                              ? "Add Manually"
                              : isActive
                                ? "Remove"
                                : "Add"}
                          </Button>
                        </InlineStack>
                      );
                    })}
                  </BlockStack>

                  <Divider />

                  <BlockStack gap="300">
                    <Text as="h4" variant="headingSm">
                      Preview & Test
                    </Text>
                    <Button
                      variant="secondary"
                      size="large"
                      onClick={() => {
                        if (shopDomain) {
                          openThemeEditorForPreview(shopDomain);
                        }
                      }}
                      disabled={
                        !shopDomain ||
                        isRefreshing ||
                        fetcher.state === "submitting"
                      }
                      loading={isRefreshing || fetcher.state === "submitting"}
                      fullWidth
                    >
                      Preview Widget
                    </Button>
                  </BlockStack>
                </BlockStack>
              </Card>
            </InlineGrid>
          </BlockStack>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
