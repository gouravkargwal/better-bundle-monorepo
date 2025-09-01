import React, { useState, useEffect } from "react";
import {
  Page,
  Layout,
  Card,
  BlockStack,
  Text,
  Button,
  Banner,
  EmptyState,
  List,
  Badge,
  Icon,
  InlineStack,
  Tabs,
  ProgressBar,
  ButtonGroup,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { MoneyIcon, ViewIcon, CartIcon } from "@shopify/polaris-icons";
import type { AnalysisState, ErrorState } from "../../types";

interface ModernDashboardProps {
  state: AnalysisState;
  error?: ErrorState;
  progress?: number;
  jobId?: string;
  isSubmitting?: boolean;
  onStartAnalysis: () => void;
  onRetry?: () => void;
}

interface BundleRecommendation {
  id: string;
  productIds: string[];
  productNames: string[];
  confidence: number;
  lift: number;
  revenue: number;
  avgOrderValue: number;
  isActive: boolean;
  discount: number;
}

interface ShopMetrics {
  totalOrders: number;
  totalRevenue: number;
  avgOrderValue: number;
  totalProducts: number;
  activeBundles: number;
  conversionRate: number;
  topPerformingBundle: {
    name: string;
    revenue: number;
    conversionRate: number;
  };
}

export function ModernDashboard({
  state,
  error,
  progress = 0,
  jobId,
  isSubmitting = false,
  onStartAnalysis,
  onRetry,
}: ModernDashboardProps) {
  const [selectedTab, setSelectedTab] = useState(0);
  const [bundleRecommendations, setBundleRecommendations] = useState<
    BundleRecommendation[]
  >([]);
  const [shopMetrics, setShopMetrics] = useState<ShopMetrics>({
    totalOrders: 0,
    totalRevenue: 0,
    avgOrderValue: 0,
    totalProducts: 0,
    activeBundles: 0,
    conversionRate: 0,
    topPerformingBundle: {
      name: "No bundles yet",
      revenue: 0,
      conversionRate: 0,
    },
  });

  // Mock data - replace with real API calls
  useEffect(() => {
    const mockBundles: BundleRecommendation[] = [
      {
        id: "1",
        productIds: ["prod_1", "prod_2"],
        productNames: ["Wireless Headphones", "Phone Case"],
        confidence: 0.85,
        lift: 2.3,
        revenue: 1250.5,
        avgOrderValue: 89.5,
        isActive: true,
        discount: 15,
      },
      {
        id: "2",
        productIds: ["prod_3", "prod_4", "prod_5"],
        productNames: ["Laptop Stand", "Wireless Mouse", "USB Hub"],
        confidence: 0.72,
        lift: 1.8,
        revenue: 890.25,
        avgOrderValue: 67.25,
        isActive: true,
        discount: 20,
      },
    ];

    const mockMetrics: ShopMetrics = {
      totalOrders: 156,
      totalRevenue: 12450.75,
      avgOrderValue: 79.81,
      totalProducts: 89,
      activeBundles: 2,
      conversionRate: 3.2,
      topPerformingBundle: {
        name: "Wireless Headphones + Phone Case",
        revenue: 1250.5,
        conversionRate: 4.1,
      },
    };

    setBundleRecommendations(mockBundles);
    setShopMetrics(mockMetrics);
  }, []);

  const tabs = [
    {
      id: "overview",
      content: "Overview",
      accessibilityLabel: "Business overview",
      panelID: "overview-panel",
    },
    {
      id: "bundles",
      content: "Product Bundles",
      accessibilityLabel: "Active bundle recommendations",
      panelID: "bundles-panel",
    },
    {
      id: "performance",
      content: "Performance",
      accessibilityLabel: "Sales and conversion metrics",
      panelID: "performance-panel",
    },
    {
      id: "insights",
      content: "Insights",
      accessibilityLabel: "Actionable business insights",
      panelID: "insights-panel",
    },
  ];

  const renderOverview = () => (
    <Layout>
      <Layout.Section>
        <Card>
          <BlockStack gap="500">
            <Text as="h2" variant="headingMd">
              🚀 Welcome to BetterBundle
            </Text>
            <Text as="p" variant="bodyMd">
              Boost your sales with AI-powered product bundle recommendations.
              We analyze your customer behavior to suggest products that sell
              better together.
            </Text>

            {state === "idle" && (
              <Button
                variant="primary"
                size="large"
                onClick={onStartAnalysis}
                disabled={isSubmitting}
                loading={isSubmitting}
              >
                {isSubmitting ? "Starting..." : "🚀 Start Bundle Analysis"}
              </Button>
            )}

            {state === "queued" && (
              <BlockStack gap="400">
                <Banner title="🔄 Analysis in Progress" tone="info">
                  <p>
                    We're analyzing your store data to find the best product
                    combinations. This usually takes 5-10 minutes.
                  </p>
                </Banner>
                <ProgressBar progress={progress} size="large" />
                <Text as="p" variant="bodySm" tone="subdued">
                  Estimated time remaining:{" "}
                  {Math.max(0, Math.ceil((100 - progress) / 10))} minutes
                </Text>
              </BlockStack>
            )}
          </BlockStack>
        </Card>
      </Layout.Section>

      <Layout.Section>
        <Card>
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd">
              📊 Your Store at a Glance
            </Text>
            <Layout>
              <Layout.Section>
                <Card padding="400">
                  <BlockStack gap="200" align="center">
                    <Icon source={MoneyIcon} />
                    <Text as="h4" variant="headingMd">
                      ${shopMetrics.totalRevenue.toLocaleString()}
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Total Revenue
                    </Text>
                  </BlockStack>
                </Card>
              </Layout.Section>
              <Layout.Section>
                <Card padding="400">
                  <BlockStack gap="200" align="center">
                    <Icon source={CartIcon} />
                    <Text variant="headingMd" as="h4">
                      {shopMetrics.totalOrders}
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Total Orders
                    </Text>
                  </BlockStack>
                </Card>
              </Layout.Section>
              <Layout.Section>
                <Card padding="400">
                  <BlockStack gap="200" align="center">
                    <Icon source={MoneyIcon} />
                    <Text as="h4" variant="headingMd">
                      {shopMetrics.conversionRate}%
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Conversion Rate
                    </Text>
                  </BlockStack>
                </Card>
              </Layout.Section>
            </Layout>
          </BlockStack>
        </Card>
      </Layout.Section>

      <Layout.Section>
        <Card>
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd">
              🎯 Top Performing Bundle
            </Text>
            <Layout>
              <Layout.Section>
                <Card padding="400">
                  <BlockStack gap="300">
                    <Text variant="headingSm" as="h4">
                      {shopMetrics.topPerformingBundle.name}
                    </Text>
                    <InlineStack gap="400">
                      <BlockStack gap="200">
                        <Text as="p" variant="bodySm" tone="subdued">
                          Revenue Generated
                        </Text>
                        <Text as="h4" variant="headingMd">
                          $
                          {shopMetrics.topPerformingBundle.revenue.toLocaleString()}
                        </Text>
                      </BlockStack>
                      <BlockStack gap="200">
                        <Text as="p" variant="bodySm" tone="subdued">
                          Conversion Rate
                        </Text>
                        <Text as="h4" variant="headingMd">
                          {shopMetrics.topPerformingBundle.conversionRate}%
                        </Text>
                      </BlockStack>
                    </InlineStack>
                  </BlockStack>
                </Card>
              </Layout.Section>
            </Layout>
          </BlockStack>
        </Card>
      </Layout.Section>
    </Layout>
  );

  const renderBundles = () => (
    <Layout>
      <Layout.Section>
        <Card>
          <BlockStack gap="400">
            <InlineStack align="space-between">
              <Text as="h3" variant="headingMd">
                🎁 Active Product Bundles
              </Text>
              <Button variant="secondary" size="medium" icon={ViewIcon}>
                View All
              </Button>
            </InlineStack>

            {bundleRecommendations.length === 0 ? (
              <EmptyState
                heading="No bundles yet"
                image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
              >
                <p>
                  Start your first analysis to discover product bundles that
                  sell better together.
                </p>
              </EmptyState>
            ) : (
              <BlockStack gap="400">
                {bundleRecommendations.map((bundle) => (
                  <Card key={bundle.id} padding="400">
                    <BlockStack gap="300">
                      <InlineStack align="space-between">
                        <Text variant="headingSm" as="h4">
                          {bundle.productNames.join(" + ")}
                        </Text>
                        <Badge tone={bundle.isActive ? "success" : "warning"}>
                          {bundle.isActive ? "Active" : "Inactive"}
                        </Badge>
                      </InlineStack>

                      <Text as="p" variant="bodySm">
                        {bundle.productNames.length} products •{" "}
                        {bundle.discount}% discount
                      </Text>

                      <Layout>
                        <Layout.Section>
                          <Card padding="400">
                            <BlockStack gap="200">
                              <Text as="p" variant="bodySm" tone="subdued">
                                Revenue Generated
                              </Text>
                              <Text as="h4" variant="headingMd">
                                ${bundle.revenue.toLocaleString()}
                              </Text>
                            </BlockStack>
                          </Card>
                        </Layout.Section>
                        <Layout.Section>
                          <Card padding="400">
                            <BlockStack gap="200">
                              <Text as="p" variant="bodySm" tone="subdued">
                                Avg Order Value
                              </Text>
                              <Text as="h4" variant="headingMd">
                                ${bundle.avgOrderValue}
                              </Text>
                            </BlockStack>
                          </Card>
                        </Layout.Section>
                        <Layout.Section>
                          <Card padding="400">
                            <BlockStack gap="200">
                              <Text as="p" variant="bodySm" tone="subdued">
                                Confidence
                              </Text>
                              <Text as="h4" variant="headingMd">
                                {(bundle.confidence * 100).toFixed(0)}%
                              </Text>
                            </BlockStack>
                          </Card>
                        </Layout.Section>
                      </Layout>

                      <InlineStack gap="200">
                        <Button variant="secondary" size="medium">
                          View Details
                        </Button>
                        <Button variant="secondary" size="medium">
                          Edit Bundle
                        </Button>
                      </InlineStack>
                    </BlockStack>
                  </Card>
                ))}
              </BlockStack>
            )}
          </BlockStack>
        </Card>
      </Layout.Section>
    </Layout>
  );

  const renderPerformance = () => (
    <Layout>
      <Layout.Section>
        <Card>
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd">
              📈 Sales Performance
            </Text>

            <Layout>
              <Layout.Section>
                <Card padding="400">
                  <BlockStack gap="300">
                    <Text variant="headingSm" as="h4">
                      💰 Revenue Metrics
                    </Text>
                    <BlockStack gap="200">
                      <InlineStack align="space-between">
                        <Text as="p" variant="bodySm">
                          Total Revenue
                        </Text>
                        <Text as="p" variant="bodyMd">
                          ${shopMetrics.totalRevenue.toLocaleString()}
                        </Text>
                      </InlineStack>
                      <InlineStack align="space-between">
                        <Text as="p" variant="bodySm">
                          Average Order Value
                        </Text>
                        <Text as="p" variant="bodyMd">
                          ${shopMetrics.avgOrderValue}
                        </Text>
                      </InlineStack>
                      <InlineStack align="space-between">
                        <Text as="p" variant="bodySm">
                          Total Orders
                        </Text>
                        <Text as="p" variant="bodyMd">
                          {shopMetrics.totalOrders}
                        </Text>
                      </InlineStack>
                    </BlockStack>
                  </BlockStack>
                </Card>
              </Layout.Section>

              <Layout.Section>
                <Card padding="400">
                  <BlockStack gap="300">
                    <Text variant="headingSm" as="h4">
                      🎯 Conversion Metrics
                    </Text>
                    <BlockStack gap="200">
                      <InlineStack align="space-between">
                        <Text as="p" variant="bodySm">
                          Overall Conversion
                        </Text>
                        <Text as="p" variant="bodyMd">
                          {shopMetrics.conversionRate}%
                        </Text>
                      </InlineStack>
                      <InlineStack align="space-between">
                        <Text as="p" variant="bodySm">
                          Active Bundles
                        </Text>
                        <Text as="p" variant="bodyMd">
                          {shopMetrics.activeBundles}
                        </Text>
                      </InlineStack>
                      <InlineStack align="space-between">
                        <Text as="p" variant="bodySm">
                          Total Products
                        </Text>
                        <Text as="p" variant="bodyMd">
                          {shopMetrics.totalProducts}
                        </Text>
                      </InlineStack>
                    </BlockStack>
                  </BlockStack>
                </Card>
              </Layout.Section>
            </Layout>
          </BlockStack>
        </Card>
      </Layout.Section>
    </Layout>
  );

  const renderInsights = () => (
    <Layout>
      <Layout.Section>
        <Card>
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd">
              💡 Actionable Insights
            </Text>

            <Layout>
              <Layout.Section>
                <Card padding="400">
                  <BlockStack gap="300">
                    <Text variant="headingSm" as="h4">
                      🚀 Quick Wins
                    </Text>
                    <List>
                      <List.Item>
                        Your "Wireless Headphones + Phone Case" bundle is
                        performing 2.3x better than individual products
                      </List.Item>
                      <List.Item>
                        Consider increasing the discount on your laptop
                        accessories bundle to boost conversions
                      </List.Item>
                      <List.Item>
                        You have 15 products that could benefit from bundle
                        recommendations
                      </List.Item>
                    </List>
                  </BlockStack>
                </Card>
              </Layout.Section>

              <Layout.Section>
                <Card padding="400">
                  <BlockStack gap="300">
                    <Text variant="headingSm" as="h4">
                      📊 Growth Opportunities
                    </Text>
                    <List>
                      <List.Item>
                        Bundle recommendations could increase your AOV by 15-25%
                      </List.Item>
                      <List.Item>
                        Consider seasonal bundles for upcoming holidays
                      </List.Item>
                      <List.Item>
                        Your conversion rate could improve by 1-2% with better
                        product placement
                      </List.Item>
                    </List>
                  </BlockStack>
                </Card>
              </Layout.Section>
            </Layout>

            <Card padding="400">
              <BlockStack gap="300">
                <Text variant="headingSm" as="h4">
                  🎯 Next Steps
                </Text>
                <ButtonGroup>
                  <Button variant="primary">Create New Bundle</Button>
                  <Button variant="secondary">View Analytics</Button>
                  <Button variant="secondary">Export Report</Button>
                </ButtonGroup>
              </BlockStack>
            </Card>
          </BlockStack>
        </Card>
      </Layout.Section>
    </Layout>
  );

  const renderTabContent = () => {
    switch (selectedTab) {
      case 0:
        return renderOverview();
      case 1:
        return renderBundles();
      case 2:
        return renderPerformance();
      case 3:
        return renderInsights();
      default:
        return renderOverview();
    }
  };

  if (state === "error" && error) {
    return (
      <Page>
        <TitleBar title="BetterBundle - Analysis Error" />
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="500" align="center">
                <Banner title={`❌ ${error.title}`} tone="critical">
                  <p>{error.description}</p>
                </Banner>

                {error.recommendations && (
                  <BlockStack gap="300">
                    <Text as="h3" variant="headingMd">
                      💡 What you can try:
                    </Text>
                    <List>
                      {error.recommendations.map((rec, index) => (
                        <List.Item key={index}>{rec}</List.Item>
                      ))}
                    </List>
                  </BlockStack>
                )}

                <BlockStack gap="300">
                  <Button
                    variant="primary"
                    onClick={onRetry || onStartAnalysis}
                  >
                    🔄 Try Again
                  </Button>
                </BlockStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  return (
    <Page>
      <TitleBar title="BetterBundle - Smart Product Bundles" />

      <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
        {renderTabContent()}
      </Tabs>
    </Page>
  );
}
