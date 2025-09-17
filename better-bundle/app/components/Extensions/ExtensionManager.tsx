import React from "react";
import {
  Card,
  Text,
  BlockStack,
  InlineStack,
  Button,
  Badge,
  Icon,
  Box,
  Divider,
  Banner,
  InlineGrid,
} from "@shopify/polaris";
import {
  CheckCircleIcon,
  AlertTriangleIcon,
  XCircleIcon,
  ExternalIcon,
  SettingsIcon,
  ThemeIcon,
  TeamIcon,
} from "@shopify/polaris-icons";
import type { ExtensionStatus } from "../../services/extension.service";

interface ExtensionManagerProps {
  extensionStatus: ExtensionStatus;
  onInstallExtension?: (extensionType: string) => void;
  onRefresh?: () => void;
  isLoading?: boolean;
}

export function ExtensionManager({
  extensionStatus,
  onInstallExtension,
  onRefresh,
  isLoading,
}: ExtensionManagerProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "active":
        return <Icon source={CheckCircleIcon} tone="success" />;
      case "inactive":
        return <Icon source={AlertTriangleIcon} tone="warning" />;
      case "not_installed":
        return <Icon source={XCircleIcon} tone="critical" />;
      default:
        return <Icon source={AlertTriangleIcon} tone="subdued" />;
    }
  };

  const getStatusTone = (status: string) => {
    switch (status) {
      case "active":
        return "success";
      case "inactive":
        return "warning";
      case "not_installed":
        return "critical";
      default:
        return "subdued";
    }
  };

  const getExtensionIcon = (extensionType: string) => {
    switch (extensionType) {
      case "web_pixel":
        // return <Icon source={AnalyticsIcon} tone="base" />;
        return "";
      case "customer_account_ui":
        return <Icon source={TeamIcon} tone="base" />;
      case "theme_extension":
        return <Icon source={ThemeIcon} tone="base" />;
      case "post_purchase":
        return <Icon source={SettingsIcon} tone="base" />;
      default:
        return <Icon source={SettingsIcon} tone="base" />;
    }
  };

  const formatLastActivity = (lastActivity?: string) => {
    if (!lastActivity) return "Never";

    const date = new Date(lastActivity);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    return `${Math.floor(diffDays / 30)} months ago`;
  };

  const activeExtensions = Object.values(extensionStatus.extensions).filter(
    (ext) => ext.status === "active",
  ).length;
  const totalExtensions = Object.keys(extensionStatus.extensions).length;

  return (
    <BlockStack gap="500">
      {/* Overall Status Banner */}
      <Banner
        tone={
          extensionStatus.overallStatus === "healthy"
            ? "success"
            : extensionStatus.overallStatus === "warning"
              ? "warning"
              : "critical"
        }
        title={`Extension Status: ${extensionStatus.overallStatus.charAt(0).toUpperCase() + extensionStatus.overallStatus.slice(1)}`}
      >
        <p>
          {activeExtensions} of {totalExtensions} extensions are active.
          {extensionStatus.overallStatus === "healthy" &&
            " All systems are running smoothly!"}
          {extensionStatus.overallStatus === "warning" &&
            " Some extensions need attention."}
          {extensionStatus.overallStatus === "critical" &&
            " Please install and configure your extensions."}
        </p>
      </Banner>

      {/* Extension Cards */}
      <InlineGrid columns={{ xs: 1, md: 2 }} gap="400">
        {Object.entries(extensionStatus.extensions).map(([key, extension]) => (
          <Card key={key}>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="start">
                <InlineStack gap="200" blockAlign="center">
                  {getExtensionIcon(extension.type)}
                  <BlockStack gap="100">
                    <Text as="h3" variant="headingMd">
                      {extension.name}
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      {extension.description}
                    </Text>
                  </BlockStack>
                </InlineStack>
                <Badge tone={getStatusTone(extension.status)}>
                  {getStatusIcon(extension.status)}
                  {extension.status.charAt(0).toUpperCase() +
                    extension.status.slice(1)}
                </Badge>
              </InlineStack>

              <Divider />

              <BlockStack gap="200">
                <InlineStack align="space-between">
                  <Text as="span" variant="bodySm" tone="subdued">
                    Last Activity
                  </Text>
                  <Text as="span" variant="bodySm">
                    {formatLastActivity(extension.last_activity)}
                  </Text>
                </InlineStack>

                <InlineStack align="space-between">
                  <Text as="span" variant="bodySm" tone="subdued">
                    Type
                  </Text>
                  <Text as="span" variant="bodySm">
                    {extension.type
                      .replace(/_/g, " ")
                      .replace(/\b\w/g, (l) => l.toUpperCase())}
                  </Text>
                </InlineStack>
              </BlockStack>

              <Divider />

              <InlineStack gap="200">
                {extension.status === "not_installed" ? (
                  <Button
                    variant="primary"
                    size="slim"
                    onClick={() => onInstallExtension?.(key)}
                    loading={isLoading}
                    disabled={isLoading}
                    fullWidth
                  >
                    Install Extension
                  </Button>
                ) : extension.status === "inactive" ? (
                  <Button
                    variant="secondary"
                    size="slim"
                    onClick={() => onInstallExtension?.(key)}
                    loading={isLoading}
                    disabled={isLoading}
                    fullWidth
                  >
                    Reactivate
                  </Button>
                ) : (
                  <Button
                    variant="tertiary"
                    size="slim"
                    url={extension.installation_url}
                    external
                    icon={ExternalIcon}
                    fullWidth
                  >
                    Manage
                  </Button>
                )}
              </InlineStack>
            </BlockStack>
          </Card>
        ))}
      </InlineGrid>

      {/* Page Status Overview */}
      <Card>
        <BlockStack gap="400">
          <InlineStack align="space-between" blockAlign="center">
            <Text as="h3" variant="headingMd">
              Page Coverage
            </Text>
            <Button
              variant="plain"
              size="slim"
              onClick={onRefresh}
              loading={isLoading}
              disabled={isLoading}
            >
              Refresh
            </Button>
          </InlineStack>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "12px",
            }}
          >
            {extensionStatus.pageStatuses.map((page) => (
              <Box
                key={page.pageType}
                padding="300"
                background="bg-surface-secondary"
                borderRadius="200"
                borderWidth="025"
                borderColor="border"
              >
                <BlockStack gap="200">
                  <InlineStack align="space-between" blockAlign="center">
                    <Text as="h4" variant="headingSm">
                      {page.pageType
                        .replace(/_/g, " ")
                        .replace(/\b\w/g, (l) => l.toUpperCase())}
                    </Text>
                    <Badge tone={page.isActive ? "success" : "critical"}>
                      {page.isActive ? "Active" : "Inactive"}
                    </Badge>
                  </InlineStack>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Extension: {page.extensionType}
                  </Text>
                  {page.lastSeen && (
                    <Text as="p" variant="bodySm" tone="subdued">
                      Last seen: {formatLastActivity(page.lastSeen)}
                    </Text>
                  )}
                </BlockStack>
              </Box>
            ))}
          </div>
        </BlockStack>
      </Card>
    </BlockStack>
  );
}
