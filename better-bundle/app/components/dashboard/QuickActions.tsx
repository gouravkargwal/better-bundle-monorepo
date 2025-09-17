import React from "react";
import { Card, Text, BlockStack, InlineStack, Button, Icon, Box } from "@shopify/polaris";
import {
  SettingsMajor,
  AnalyticsMajor,
  BillingMajor,
  RefreshMajor,
  ViewMajor,
  EditMajor,
} from "@shopify/polaris-icons";

interface QuickActionsProps {
  onRefresh?: () => void;
  isLoading?: boolean;
}

export function QuickActions({ onRefresh, isLoading }: QuickActionsProps) {
  const actions = [
    {
      title: "Configure Extensions",
      description: "Manage your recommendation widgets",
      icon: SettingsMajor,
      url: "/app/widget-config",
      variant: "primary" as const,
    },
    {
      title: "View Analytics",
      description: "Check performance metrics",
      icon: AnalyticsMajor,
      url: "/app/dashboard",
      variant: "secondary" as const,
    },
    {
      title: "Billing & Performance",
      description: "Review your billing and ROI",
      icon: BillingMajor,
      url: "/app/billing",
      variant: "tertiary" as const,
    },
  ];

  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack align="space-between" blockAlign="center">
          <Text as="h3" variant="headingMd">
            Quick Actions
          </Text>
          {onRefresh && (
            <Button
              variant="plain"
              size="slim"
              icon={RefreshMajor}
              onClick={onRefresh}
              loading={isLoading}
              disabled={isLoading}
            >
              Refresh
            </Button>
          )}
        </InlineStack>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          {actions.map((action) => (
            <Box
              key={action.title}
              padding="400"
              background="bg-surface-secondary"
              borderRadius="200"
              borderWidth="025"
              borderColor="border"
            >
              <BlockStack gap="300">
                <InlineStack gap="200" blockAlign="center">
                  <Icon source={action.icon} tone="base" />
                  <Text as="h4" variant="headingSm">
                    {action.title}
                  </Text>
                </InlineStack>
                <Text as="p" variant="bodySm" tone="subdued">
                  {action.description}
                </Text>
                <Button
                  url={action.url}
                  variant={action.variant}
                  size="slim"
                  fullWidth
                >
                  {action.variant === "primary" ? "Configure" : 
                   action.variant === "secondary" ? "View" : "Review"}
                </Button>
              </BlockStack>
            </Box>
          ))}
        </div>

        {/* Additional Quick Actions */}
        <BlockStack gap="300">
          <Text as="h4" variant="headingSm">
            Additional Tools
          </Text>
          <InlineStack gap="300" wrap={false}>
            <Button
              variant="tertiary"
              size="slim"
              icon={ViewMajor}
              url="/app/widget-config"
            >
              Preview Widgets
            </Button>
            <Button
              variant="tertiary"
              size="slim"
              icon={EditMajor}
              url="/app/widget-config"
            >
              Customize Settings
            </Button>
            <Button
              variant="tertiary"
              size="slim"
              icon={AnalyticsMajor}
              url="/app/dashboard"
            >
              Export Data
            </Button>
          </InlineStack>
        </BlockStack>
      </BlockStack>
    </Card>
  );
}
