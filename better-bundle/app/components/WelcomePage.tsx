import React from "react";
import {
  Page,
  Layout,
  Text,
  Card,
  Button,
  BlockStack,
  InlineStack,
  Badge,
  Icon,
  Box,
  Divider,
  Link,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import {
  AnalyticsMajor,
  SettingsMajor,
  BillingMajor,
  StarFilledMajor,
  ArrowRightMajor,
  CheckCircleMajor,
} from "@shopify/polaris-icons";
import { formatCurrency } from "../utils/currency";
import type { DashboardOverview } from "../services/dashboard.service";

interface WelcomePageProps {
  dashboardData: any;
  shop: string;
  isNewUser: boolean;
  error?: string;
}

export function WelcomePage({
  dashboardData,
  shop,
  isNewUser,
  error,
}: WelcomePageProps) {
  const shopName = shop.replace(".myshopify.com", "");

  if (error) {
    return (
      <Page>
        <TitleBar title="Welcome to BetterBundle" />
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="400" align="center">
                <Text as="h2" variant="headingLg" tone="critical">
                  Unable to load data
                </Text>
                <Text as="p" variant="bodyMd" tone="subdued">
                  {error}
                </Text>
                <Button url="/app/dashboard" variant="primary">
                  Go to Dashboard
                </Button>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  return (
    <Page>
      <TitleBar title="Welcome to BetterBundle" />
      <BlockStack gap="500">
        {/* Hero Section */}
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <InlineStack align="space-between" blockAlign="start">
                  <BlockStack gap="200">
                    <Text as="h1" variant="heading2xl">
                      Welcome to BetterBundle, {shopName}! 🎉
                    </Text>
                    <Text as="p" variant="bodyLg" tone="subdued">
                      AI-powered product recommendations that boost your sales
                      and enhance customer experience.
                    </Text>
                  </BlockStack>
                  <Badge tone="success" size="large">
                    <Icon source={StarFilledMajor} />
                    Active
                  </Badge>
                </InlineStack>

                {isNewUser ? (
                  <BlockStack gap="300">
                    <Text as="h3" variant="headingMd">
                      Let's get you started in 3 simple steps:
                    </Text>
                    <InlineStack gap="400" wrap={false}>
                      <Card>
                        <BlockStack gap="200" align="center">
                          <Box
                            padding="300"
                            background="bg-surface-brand"
                            borderRadius="200"
                          >
                            <Text as="span" variant="headingLg" tone="base">
                              1
                            </Text>
                          </Box>
                          <Text as="h4" variant="headingSm">
                            Install Extensions
                          </Text>
                          <Text
                            as="p"
                            variant="bodySm"
                            tone="subdued"
                            alignment="center"
                          >
                            Add our recommendation widgets to your store pages
                          </Text>
                        </BlockStack>
                      </Card>
                      <Card>
                        <BlockStack gap="200" align="center">
                          <Box
                            padding="300"
                            background="bg-surface-brand"
                            borderRadius="200"
                          >
                            <Text as="span" variant="headingLg" tone="base">
                              2
                            </Text>
                          </Box>
                          <Text as="h4" variant="headingSm">
                            Configure Settings
                          </Text>
                          <Text
                            as="p"
                            variant="bodySm"
                            tone="subdued"
                            alignment="center"
                          >
                            Customize how recommendations appear to your
                            customers
                          </Text>
                        </BlockStack>
                      </Card>
                      <Card>
                        <BlockStack gap="200" align="center">
                          <Box
                            padding="300"
                            background="bg-surface-brand"
                            borderRadius="200"
                          >
                            <Text as="span" variant="headingLg" tone="base">
                              3
                            </Text>
                          </Box>
                          <Text as="h4" variant="headingSm">
                            Watch Sales Grow
                          </Text>
                          <Text
                            as="p"
                            variant="bodySm"
                            tone="subdued"
                            alignment="center"
                          >
                            Monitor performance and optimize your
                            recommendations
                          </Text>
                        </BlockStack>
                      </Card>
                    </InlineStack>
                  </BlockStack>
                ) : (
                  <BlockStack gap="300">
                    <Text as="h3" variant="headingMd">
                      Your recommendation performance this month:
                    </Text>
                    <InlineStack gap="400" wrap={false}>
                      <Card>
                        <BlockStack gap="200">
                          <Text as="h4" variant="headingSm" tone="subdued">
                            Revenue Generated
                          </Text>
                          <Text as="p" variant="headingLg">
                            {formatCurrency(
                              dashboardData.overview.total_revenue,
                              dashboardData.overview.currency_code,
                            )}
                          </Text>
                        </BlockStack>
                      </Card>
                      <Card>
                        <BlockStack gap="200">
                          <Text as="h4" variant="headingSm" tone="subdued">
                            Conversion Rate
                          </Text>
                          <Text as="p" variant="headingLg">
                            {dashboardData.overview.conversion_rate.toFixed(1)}%
                          </Text>
                        </BlockStack>
                      </Card>
                      <Card>
                        <BlockStack gap="200">
                          <Text as="h4" variant="headingSm" tone="subdued">
                            Recommendations Shown
                          </Text>
                          <Text as="p" variant="headingLg">
                            {dashboardData.overview.total_recommendations.toLocaleString()}
                          </Text>
                        </BlockStack>
                      </Card>
                    </InlineStack>
                  </BlockStack>
                )}

                <Divider />

                <InlineStack gap="300">
                  <Button
                    url="/app/widget-config"
                    variant="primary"
                    size="large"
                    icon={SettingsMajor}
                  >
                    {isNewUser ? "Get Started" : "Manage Extensions"}
                  </Button>
                  <Button
                    url="/app/dashboard"
                    variant="secondary"
                    size="large"
                    icon={AnalyticsMajor}
                  >
                    View Analytics
                  </Button>
                  {!isNewUser && (
                    <Button
                      url="/app/billing"
                      variant="tertiary"
                      size="large"
                      icon={BillingMajor}
                    >
                      Billing & Performance
                    </Button>
                  )}
                </InlineStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>

        {/* Quick Actions */}
        <Layout>
          <Layout.Section variant="oneHalf">
            <Card>
              <BlockStack gap="400">
                <Text as="h3" variant="headingMd">
                  Quick Actions
                </Text>
                <BlockStack gap="300">
                  <InlineStack align="space-between" blockAlign="center">
                    <InlineStack gap="200" blockAlign="center">
                      <Icon source={SettingsMajor} tone="base" />
                      <Text as="p" variant="bodyMd">
                        Configure Extensions
                      </Text>
                    </InlineStack>
                    <Button
                      url="/app/widget-config"
                      variant="plain"
                      size="slim"
                      icon={ArrowRightMajor}
                    >
                      Configure
                    </Button>
                  </InlineStack>
                  <InlineStack align="space-between" blockAlign="center">
                    <InlineStack gap="200" blockAlign="center">
                      <Icon source={AnalyticsMajor} tone="base" />
                      <Text as="p" variant="bodyMd">
                        View Performance
                      </Text>
                    </InlineStack>
                    <Button
                      url="/app/dashboard"
                      variant="plain"
                      size="slim"
                      icon={ArrowRightMajor}
                    >
                      View
                    </Button>
                  </InlineStack>
                  {!isNewUser && (
                    <InlineStack align="space-between" blockAlign="center">
                      <InlineStack gap="200" blockAlign="center">
                        <Icon source={BillingMajor} tone="base" />
                        <Text as="p" variant="bodyMd">
                          Check Billing
                        </Text>
                      </InlineStack>
                      <Button
                        url="/app/billing"
                        variant="plain"
                        size="slim"
                        icon={ArrowRightMajor}
                      >
                        View
                      </Button>
                    </InlineStack>
                  )}
                </BlockStack>
              </BlockStack>
            </Card>
          </Layout.Section>

          <Layout.Section variant="oneHalf">
            <Card>
              <BlockStack gap="400">
                <Text as="h3" variant="headingMd">
                  What's New
                </Text>
                <BlockStack gap="300">
                  <InlineStack gap="200" blockAlign="start">
                    <Icon source={CheckCircleMajor} tone="success" />
                    <BlockStack gap="100">
                      <Text as="p" variant="bodyMd">
                        Unified Analytics System
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Track performance across all extensions with our new
                        unified analytics
                      </Text>
                    </BlockStack>
                  </InlineStack>
                  <InlineStack gap="200" blockAlign="start">
                    <Icon source={CheckCircleMajor} tone="success" />
                    <BlockStack gap="100">
                      <Text as="p" variant="bodyMd">
                        Pay-as-Performance Billing
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Only pay for the revenue you actually generate through
                        recommendations
                      </Text>
                    </BlockStack>
                  </InlineStack>
                  <InlineStack gap="200" blockAlign="start">
                    <Icon source={CheckCircleMajor} tone="success" />
                    <BlockStack gap="100">
                      <Text as="p" variant="bodyMd">
                        Enhanced AI Recommendations
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Improved algorithms for better product matching and
                        higher conversions
                      </Text>
                    </BlockStack>
                  </InlineStack>
                </BlockStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>

        {/* Help Section */}
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text as="h3" variant="headingMd">
                  Need Help?
                </Text>
                <InlineStack gap="400" wrap={false}>
                  <BlockStack gap="200">
                    <Text as="h4" variant="headingSm">
                      Getting Started
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Learn how to set up and configure your recommendation
                      widgets
                    </Text>
                    <Button variant="tertiary" size="slim">
                      View Guide
                    </Button>
                  </BlockStack>
                  <BlockStack gap="200">
                    <Text as="h4" variant="headingSm">
                      Best Practices
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Tips and strategies to maximize your recommendation
                      performance
                    </Text>
                    <Button variant="tertiary" size="slim">
                      Learn More
                    </Button>
                  </BlockStack>
                  <BlockStack gap="200">
                    <Text as="h4" variant="headingSm">
                      Support
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Get help from our support team or community
                    </Text>
                    <Button variant="tertiary" size="slim">
                      Contact Support
                    </Button>
                  </BlockStack>
                </InlineStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
