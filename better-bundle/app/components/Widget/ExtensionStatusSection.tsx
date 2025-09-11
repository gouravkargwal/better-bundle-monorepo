import React, { useState, useEffect } from "react";
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

export function ExtensionStatusSection() {
  const [extensionStatus, setExtensionStatus] =
    useState<ExtensionStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  useEffect(() => {
    checkExtensionStatus();
  }, []);

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
      setIsRefreshing(false);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
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

  const getStatusBadge = () => {
    if (isLoading) {
      return <Badge tone="info">Checking...</Badge>;
    }

    if (!extensionStatus) {
      return <Badge tone="critical">Error</Badge>;
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
      return "Unable to check installation status.";
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
              onClick={handleRefresh}
              loading={isRefreshing}
              disabled={isLoading}
            >
              Refresh
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

            {/* Show active pages in a friendly way */}
            {extensionStatus?.pageStatuses &&
              extensionStatus.pageStatuses.length > 0 && (
                <Box padding="200" background="bg-surface" borderRadius="100">
                  <Text as="p" variant="bodySm" fontWeight="medium">
                    Active on:
                  </Text>
                  <InlineStack gap="100" wrap={true}>
                    {extensionStatus.pageStatuses
                      .slice(0, 4) // Show only main theme pages
                      .filter((page) => page.isActive)
                      .map((page, index) => (
                        <Badge
                          key={`${page.pageType}-${index}`}
                          tone="success"
                          size="small"
                        >
                          {getPageDisplayName(page.pageType)}
                        </Badge>
                      ))}
                    {extensionStatus.pageStatuses
                      .slice(0, 4)
                      .filter((page) => page.isActive).length === 0 && (
                      <Text as="span" variant="bodySm" tone="subdued">
                        No pages currently active
                      </Text>
                    )}
                  </InlineStack>
                </Box>
              )}
          </Box>
        )}

        {/* Action Buttons */}
        <InlineStack gap="200">
          <Button url="/admin/themes" external variant="primary">
            {extensionStatus?.isInstalled
              ? "Manage in Theme Editor"
              : "Open Theme Editor"}
          </Button>
          {extensionStatus?.isInstalled && (
            <Button url="/app/widget-config" variant="secondary">
              Configure Widget
            </Button>
          )}
        </InlineStack>
      </BlockStack>
    </Card>
  );
}
