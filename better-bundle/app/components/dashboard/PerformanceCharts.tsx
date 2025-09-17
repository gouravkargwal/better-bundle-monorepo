import React from "react";
import {
  Card,
  Text,
  BlockStack,
  InlineStack,
  Badge,
  Box,
} from "@shopify/polaris";
import { formatCurrency } from "../../utils/currency";

interface PerformanceChartsProps {
  data: {
    revenue_trend: Array<{ date: string; value: number }>;
    conversion_trend: Array<{ date: string; value: number }>;
    top_performing_extensions: Array<{
      name: string;
      revenue: number;
      conversion_rate: number;
    }>;
  };
  currency_code: string;
}

export function PerformanceCharts({
  data,
  currency_code,
}: PerformanceChartsProps) {
  // Simple chart component using CSS and basic styling
  const SimpleChart = ({
    data,
    color,
    height = 100,
  }: {
    data: Array<{ date: string; value: number }>;
    color: string;
    height?: number;
  }) => {
    const maxValue = Math.max(...data.map((d) => d.value));
    const minValue = Math.min(...data.map((d) => d.value));
    const range = maxValue - minValue;

    return (
      <Box
        padding="300"
        background="bg-surface-secondary"
        borderRadius="200"
        borderWidth="025"
        borderColor="border"
      >
        <div
          style={{
            height: `${height}px`,
            display: "flex",
            alignItems: "end",
            gap: "4px",
            padding: "8px 0",
          }}
        >
          {data.map((point, index) => {
            const heightPercent =
              range > 0 ? ((point.value - minValue) / range) * 100 : 50;
            return (
              <div
                key={index}
                style={{
                  flex: 1,
                  height: `${heightPercent}%`,
                  backgroundColor: color,
                  borderRadius: "2px 2px 0 0",
                  minHeight: "4px",
                  transition: "all 0.3s ease",
                }}
                title={`${point.date}: ${point.value.toFixed(1)}`}
              />
            );
          })}
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: "12px",
            color: "#6B7280",
            marginTop: "8px",
          }}
        >
          <span>{data[0]?.date}</span>
          <span>{data[data.length - 1]?.date}</span>
        </div>
      </Box>
    );
  };

  return (
    <BlockStack gap="500">
      <Text as="h2" variant="headingLg">
        Performance Trends
      </Text>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "16px",
        }}
      >
        {/* Revenue Trend */}
        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between" blockAlign="center">
              <Text as="h3" variant="headingMd">
                Revenue Trend
              </Text>
              <Badge tone="success">
                {data.revenue_trend.length > 1
                  ? `${(((data.revenue_trend[data.revenue_trend.length - 1].value - data.revenue_trend[0].value) / data.revenue_trend[0].value) * 100).toFixed(1)}%`
                  : "New"}
              </Badge>
            </InlineStack>
            <SimpleChart
              data={data.revenue_trend}
              color="#10B981"
              height={120}
            />
            <InlineStack align="space-between">
              <Text as="span" variant="bodySm" tone="subdued">
                Last 7 days
              </Text>
              <Text as="span" variant="bodySm" tone="subdued">
                {formatCurrency(
                  data.revenue_trend[data.revenue_trend.length - 1]?.value || 0,
                  currency_code,
                )}
              </Text>
            </InlineStack>
          </BlockStack>
        </Card>

        {/* Conversion Trend */}
        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between" blockAlign="center">
              <Text as="h3" variant="headingMd">
                Conversion Rate
              </Text>
              <Badge tone="info">
                {data.conversion_trend.length > 1
                  ? `${(((data.conversion_trend[data.conversion_trend.length - 1].value - data.conversion_trend[0].value) / data.conversion_trend[0].value) * 100).toFixed(1)}%`
                  : "New"}
              </Badge>
            </InlineStack>
            <SimpleChart
              data={data.conversion_trend}
              color="#3B82F6"
              height={120}
            />
            <InlineStack align="space-between">
              <Text as="span" variant="bodySm" tone="subdued">
                Last 7 days
              </Text>
              <Text as="span" variant="bodySm" tone="subdued">
                {data.conversion_trend[
                  data.conversion_trend.length - 1
                ]?.value.toFixed(1)}
                %
              </Text>
            </InlineStack>
          </BlockStack>
        </Card>
      </div>

      {/* Top Performing Extensions */}
      <Card>
        <BlockStack gap="400">
          <Text as="h3" variant="headingMd">
            Top Performing Extensions
          </Text>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
              gap: "16px",
            }}
          >
            {data.top_performing_extensions.map((extension, index) => (
              <Box
                key={extension.name}
                padding="400"
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
                    <Badge
                      tone={
                        index === 0
                          ? "success"
                          : index === 1
                            ? "info"
                            : "warning"
                      }
                    >
                      #{index + 1}
                    </Badge>
                  </InlineStack>
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodySm" tone="subdued">
                      Revenue
                    </Text>
                    <Text as="span" variant="bodySm">
                      {formatCurrency(extension.revenue, currency_code)}
                    </Text>
                  </InlineStack>
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodySm" tone="subdued">
                      Conversion
                    </Text>
                    <Text as="span" variant="bodySm">
                      {extension.conversion_rate.toFixed(1)}%
                    </Text>
                  </InlineStack>
                </BlockStack>
              </Box>
            ))}
          </div>
        </BlockStack>
      </Card>
    </BlockStack>
  );
}
