import React from "react";
import { Card, Text, BlockStack, InlineStack, Badge, Icon, Box } from "@shopify/polaris";
import { CheckCircleMajor, AlertTriangleMajor, ClockMajor } from "@shopify/polaris-icons";

interface StatusOverviewProps {
  data: {
    system_health: "healthy" | "warning" | "critical";
    extensions_status: Array<{
      name: string;
      status: "active" | "inactive" | "error";
      last_activity: string;
    }>;
    data_sync_status: {
      last_sync: string;
      sync_frequency: string;
      status: "synced" | "syncing" | "error";
    };
    performance_metrics: {
      response_time: number;
      uptime: number;
      error_rate: number;
    };
  };
}

export function StatusOverview({ data }: StatusOverviewProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "healthy":
      case "active":
      case "synced":
        return <Icon source={CheckCircleMajor} tone="success" />;
      case "warning":
      case "syncing":
        return <Icon source={ClockMajor} tone="warning" />;
      case "critical":
      case "error":
      case "inactive":
        return <Icon source={AlertTriangleMajor} tone="critical" />;
      default:
        return <Icon source={ClockMajor} tone="subdued" />;
    }
  };

  const getStatusTone = (status: string) => {
    switch (status) {
      case "healthy":
      case "active":
      case "synced":
        return "success";
      case "warning":
      case "syncing":
        return "warning";
      case "critical":
      case "error":
      case "inactive":
        return "critical";
      default:
        return "subdued";
    }
  };

  const formatUptime = (uptime: number) => {
    if (uptime >= 99.9) return "99.9%";
    return `${uptime.toFixed(1)}%`;
  };

  const formatResponseTime = (time: number) => {
    if (time < 1000) return `${time}ms`;
    return `${(time / 1000).toFixed(1)}s`;
  };

  return (
    <BlockStack gap="400">
      <Text as="h2" variant="headingLg">
        System Status
      </Text>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
        {/* Overall System Health */}
        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between" blockAlign="center">
              <Text as="h3" variant="headingMd">
                System Health
              </Text>
              <Badge tone={getStatusTone(data.system_health)}>
                {getStatusIcon(data.system_health)}
                {data.system_health.charAt(0).toUpperCase() + data.system_health.slice(1)}
              </Badge>
            </InlineStack>
            
            <BlockStack gap="200">
              <InlineStack align="space-between">
                <Text as="span" variant="bodySm" tone="subdued">
                  Uptime
                </Text>
                <Text as="span" variant="bodySm">
                  {formatUptime(data.performance_metrics.uptime)}
                </Text>
              </InlineStack>
              <InlineStack align="space-between">
                <Text as="span" variant="bodySm" tone="subdued">
                  Response Time
                </Text>
                <Text as="span" variant="bodySm">
                  {formatResponseTime(data.performance_metrics.response_time)}
                </Text>
              </InlineStack>
              <InlineStack align="space-between">
                <Text as="span" variant="bodySm" tone="subdued">
                  Error Rate
                </Text>
                <Text as="span" variant="bodySm">
                  {data.performance_metrics.error_rate.toFixed(2)}%
                </Text>
              </InlineStack>
            </BlockStack>
          </BlockStack>
        </Card>

        {/* Data Sync Status */}
        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between" blockAlign="center">
              <Text as="h3" variant="headingMd">
                Data Sync
              </Text>
              <Badge tone={getStatusTone(data.data_sync_status.status)}>
                {getStatusIcon(data.data_sync_status.status)}
                {data.data_sync_status.status.charAt(0).toUpperCase() + data.data_sync_status.status.slice(1)}
              </Badge>
            </InlineStack>
            
            <BlockStack gap="200">
              <InlineStack align="space-between">
                <Text as="span" variant="bodySm" tone="subdued">
                  Last Sync
                </Text>
                <Text as="span" variant="bodySm">
                  {new Date(data.data_sync_status.last_sync).toLocaleString()}
                </Text>
              </InlineStack>
              <InlineStack align="space-between">
                <Text as="span" variant="bodySm" tone="subdued">
                  Frequency
                </Text>
                <Text as="span" variant="bodySm">
                  {data.data_sync_status.sync_frequency}
                </Text>
              </InlineStack>
            </BlockStack>
          </BlockStack>
        </Card>
      </div>

      {/* Extensions Status */}
      <Card>
        <BlockStack gap="400">
          <Text as="h3" variant="headingMd">
            Extensions Status
          </Text>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
            {data.extensions_status.map((extension) => (
              <Box
                key={extension.name}
                padding="300"
                background="bg-surface-secondary"
                borderRadius="200"
                borderWidth="025"
                borderColor="border"
              >
                <BlockStack gap="200">
                  <InlineStack align="space-between" blockAlign="center">
                    <Text as="h4" variant="headingSm">
                      {extension.name}
                    </Text>
                    <Badge tone={getStatusTone(extension.status)} size="small">
                      {getStatusIcon(extension.status)}
                      {extension.status.charAt(0).toUpperCase() + extension.status.slice(1)}
                    </Badge>
                  </InlineStack>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Last activity: {new Date(extension.last_activity).toLocaleDateString()}
                  </Text>
                </BlockStack>
              </Box>
            ))}
          </div>
        </BlockStack>
      </Card>
    </BlockStack>
  );
}
