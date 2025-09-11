import React, { useState } from "react";
import { useNavigate } from "@remix-run/react";
import {
  Card,
  BlockStack,
  Text,
  Button,
  Badge,
  Box,
  InlineStack,
} from "@shopify/polaris";

interface PageStatus {
  pageType: string;
  isActive: boolean;
  templateFile?: string;
  sectionName?: string;
  configuration?: any;
}

interface ThemeStatus {
  themeId: string;
  themeName: string;
  role: string;
  hasAppBlocks: boolean;
  locations: string[];
  pageStatuses: PageStatus[];
  error?: string;
}

interface ExtensionStatus {
  isInstalled: boolean;
  isAvailable: boolean;
  lastChecked: Date;
  error?: string;
  blockUsage?: {
    hasAppBlocks: boolean;
    locations: string[];
  };
  pageStatuses?: PageStatus[];
  pageConfigs?: Record<string, any>;
  themeId?: string;
  themeName?: string;
  shopDomain?: string;
  multiThemeStatus?: ThemeStatus[];
}

interface ExtensionStatusSectionProps {
  config?: any; // Widget configuration from parent
}

export function ExtensionStatusSection({
  config,
}: ExtensionStatusSectionProps) {
  const [extensionStatus, setExtensionStatus] =
    useState<ExtensionStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const checkExtensionStatus = async () => {
    try {
      const response = await fetch("/app/api/extension-status");
      const data = await response.json();

      if (data.success) {
        setExtensionStatus(data.status);
      } else {
        console.error("Failed to fetch extension status:", data.error);
      }
    } catch (error) {
      console.error("Error checking extension status:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCheckStatus = async () => {
    setIsLoading(true);
    await checkExtensionStatus();
  };

  const getPageDisplayName = (pageType: string): string => {
    const displayNames: Record<string, string> = {
      product_page: "Product Pages",
      homepage: "Homepage",
      collection: "Collection Pages",
      cart_page: "Cart Page",
    };
    return displayNames[pageType] || pageType;
  };

  // Compare widget config with actual installation status
  const getConfigurationGap = () => {
    if (!extensionStatus) return null;

    const workingPages = [];
    const missingPages = [];

    // Use the current config from extension status instead of stale prop
    const currentConfig = extensionStatus.pageConfigs || {};

    // Check each page type
    const pageTypes = [
      { key: "product_page", configKey: "product_page" },
      { key: "cart_page", configKey: "cart_page" },
      { key: "homepage", configKey: "homepage" },
      { key: "collection", configKey: "collection" },
    ];

    for (const pageType of pageTypes) {
      const isEnabledInConfig = currentConfig[pageType.configKey]?.enabled;

      // Find the ACTIVE page status (not just any page status)
      const activePageStatus = extensionStatus.pageStatuses?.find(
        (p) => p.pageType === pageType.key && p.isActive === true,
      );

      const isActiveInTheme = !!activePageStatus;

      if (isEnabledInConfig) {
        if (isActiveInTheme) {
          workingPages.push(getPageDisplayName(pageType.key));
        } else {
          missingPages.push(getPageDisplayName(pageType.key));
        }
      }
    }

    return { workingPages, missingPages };
  };

  const getStatusBadge = () => {
    if (isLoading) {
      return <Badge tone="info">Checking...</Badge>;
    }

    if (!extensionStatus) {
      return <Badge tone="info">Not Checked</Badge>;
    }

    if (extensionStatus.isInstalled) {
      return <Badge tone="success">Installed</Badge>;
    } else if (extensionStatus.isAvailable) {
      return <Badge tone="warning">Available</Badge>;
    } else {
      return <Badge tone="critical">Not Available</Badge>;
    }
  };

  const getStatusMessage = () => {
    if (isLoading) {
      return "Checking installation status...";
    }

    if (!extensionStatus) {
      return "Click 'Check Status' to verify if the extension is installed in your theme.";
    }

    if (extensionStatus.isInstalled) {
      const activePages =
        extensionStatus.pageStatuses?.filter((page) => page.isActive) || [];

      if (activePages.length > 0) {
        return `✅ Widget is active on ${activePages.length} page type${activePages.length > 1 ? "s" : ""}!`;
      }
      return "✅ Your recommendations widget is installed and active!";
    } else if (extensionStatus.isAvailable) {
      return "⚠️ Extension is available but not yet installed in your theme.";
    } else {
      return "❌ Extension is not available. Please ensure the app is properly installed.";
    }
  };

  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack align="space-between" blockAlign="center">
          <Text as="h3" variant="headingMd" fontWeight="semibold">
            📊 Extension Status
          </Text>
          <InlineStack gap="200" blockAlign="center">
            {getStatusBadge()}
            <Button
              size="slim"
              onClick={handleCheckStatus}
              loading={isLoading}
              variant="primary"
            >
              Check Status
            </Button>
          </InlineStack>
        </InlineStack>

        <Text as="p" variant="bodyMd">
          {getStatusMessage()}
        </Text>

        {extensionStatus?.error && (
          <Box
            background="bg-surface-critical"
            padding="300"
            borderRadius="200"
          >
            <Text as="p" variant="bodySm" tone="critical">
              <strong>Error:</strong> {extensionStatus.error}
            </Text>
          </Box>
        )}

        {extensionStatus?.lastChecked && (
          <Text as="p" variant="bodySm" tone="subdued">
            Last checked:{" "}
            {new Date(extensionStatus.lastChecked).toLocaleString()}
          </Text>
        )}

        {/* Simple Status Summary */}
        {extensionStatus?.isInstalled === false &&
          extensionStatus?.isAvailable === true && (
            <Box
              background="bg-surface-warning"
              padding="300"
              borderRadius="200"
            >
              <Text as="p" variant="bodyMd">
                <strong>Next Step:</strong> Add the extension to your theme
                using the installation guide below.
              </Text>
            </Box>
          )}

        {extensionStatus?.isInstalled === true && (
          <Box background="bg-surface-success" padding="300" borderRadius="200">
            <Text as="p" variant="bodyMd">
              <strong>Great!</strong> The extension is installed and active on
              your theme.
            </Text>

            {/* Show configuration gap analysis */}
            {(() => {
              const gap = getConfigurationGap();
              if (!gap) return null;

              return (
                <Box padding="200" background="bg-surface" borderRadius="100">
                  <Text as="p" variant="bodySm" fontWeight="medium">
                    Configuration Status:
                  </Text>

                  {/* Pages that are enabled and working */}
                  {gap.workingPages.length > 0 && (
                    <Box padding="100">
                      <Text as="p" variant="bodySm" tone="success">
                        ✅ Working: {gap.workingPages.join(", ")}
                      </Text>
                    </Box>
                  )}

                  {/* Pages that are enabled but not installed */}
                  {gap.missingPages.length > 0 && (
                    <Box padding="100">
                      <Text as="p" variant="bodySm" tone="critical">
                        ⚠️ Configured but not installed:{" "}
                        {gap.missingPages.join(", ")}
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        These pages are enabled in your settings but the widget
                        isn't added to them yet.
                      </Text>
                    </Box>
                  )}
                </Box>
              );
            })()}
          </Box>
        )}
      </BlockStack>
    </Card>
  );
}
