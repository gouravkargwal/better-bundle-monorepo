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
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import {
  SettingsIcon,
  BillIcon,
  StarFilledIcon,
  ArrowRightIcon,
  CheckCircleIcon,
  CashDollarIcon,
  EyeCheckMarkIcon,
} from "@shopify/polaris-icons";
import { formatCurrency } from "../utils/currency";

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
            <BlockStack gap="400">
              {/* Dashboard-style header */}
              <div
                style={{
                  padding: "24px",
                  backgroundColor: "#F0F9FF",
                  borderRadius: "12px",
                  border: "1px solid #BAE6FD",
                }}
              >
                <div style={{ color: "#0C4A6E" }}>
                  <Text as="h1" variant="heading2xl" fontWeight="bold">
                    Welcome to BetterBundle, {shopName}! 🎉
                  </Text>
                </div>
                <div style={{ marginTop: "8px" }}>
                  <Text as="p" variant="bodyLg" tone="subdued">
                    AI-powered product recommendations that boost your sales and
                    enhance customer experience.
                  </Text>
                </div>
                <div style={{ marginTop: "16px" }}>
                  <Badge tone="success" size="large">
                    Active
                  </Badge>
                </div>
              </div>

              <Card>
                <BlockStack gap="400">
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
                      <div
                        style={{
                          padding: "24px",
                          backgroundColor: "#F8FAFC",
                          borderRadius: "12px",
                          border: "1px solid #E2E8F0",
                        }}
                      >
                        <div style={{ color: "#1E293B" }}>
                          <Text as="h3" variant="headingMd" fontWeight="bold">
                            📊 Your Performance This Month
                          </Text>
                        </div>
                        <div style={{ marginTop: "8px" }}>
                          <Text as="p" variant="bodyMd" tone="subdued">
                            Key metrics from your recommendation extensions
                          </Text>
                        </div>
                      </div>

                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns:
                            "repeat(auto-fit, minmax(200px, 1fr))",
                          gap: "16px",
                          alignItems: "stretch",
                        }}
                      >
                        <div
                          style={{
                            transition: "all 0.2s ease-in-out",
                            cursor: "pointer",
                            borderRadius: "8px",
                            overflow: "hidden",
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.transform =
                              "translateY(-2px)";
                            e.currentTarget.style.boxShadow =
                              "0 8px 25px rgba(0,0,0,0.1)";
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.transform = "translateY(0)";
                            e.currentTarget.style.boxShadow = "none";
                          }}
                        >
                          <Card>
                            <div style={{ minHeight: "100px", padding: "4px" }}>
                              <BlockStack gap="300">
                                <InlineStack
                                  align="space-between"
                                  blockAlign="center"
                                >
                                  <BlockStack gap="100">
                                    <Text
                                      as="h4"
                                      variant="headingSm"
                                      tone="subdued"
                                      fontWeight="medium"
                                    >
                                      Revenue Generated
                                    </Text>
                                  </BlockStack>
                                  <div
                                    style={{
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      minWidth: "36px",
                                      minHeight: "36px",
                                      padding: "10px",
                                      backgroundColor: "#10B98115",
                                      borderRadius: "12px",
                                      border: "2px solid #10B98130",
                                    }}
                                  >
                                    <Icon source={CashDollarIcon} tone="base" />
                                  </div>
                                </InlineStack>
                                <div style={{ color: "#10B981" }}>
                                  <Text
                                    as="p"
                                    variant="headingLg"
                                    fontWeight="bold"
                                  >
                                    {formatCurrency(
                                      dashboardData.overview.total_revenue,
                                      dashboardData.overview.currency_code,
                                    )}
                                  </Text>
                                </div>
                              </BlockStack>
                            </div>
                          </Card>
                        </div>

                        <div
                          style={{
                            transition: "all 0.2s ease-in-out",
                            cursor: "pointer",
                            borderRadius: "8px",
                            overflow: "hidden",
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.transform =
                              "translateY(-2px)";
                            e.currentTarget.style.boxShadow =
                              "0 8px 25px rgba(0,0,0,0.1)";
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.transform = "translateY(0)";
                            e.currentTarget.style.boxShadow = "none";
                          }}
                        >
                          <Card>
                            <div style={{ minHeight: "100px", padding: "4px" }}>
                              <BlockStack gap="300">
                                <InlineStack
                                  align="space-between"
                                  blockAlign="center"
                                >
                                  <BlockStack gap="100">
                                    <Text
                                      as="h4"
                                      variant="headingSm"
                                      tone="subdued"
                                      fontWeight="medium"
                                    >
                                      Conversion Rate
                                    </Text>
                                  </BlockStack>
                                  <div
                                    style={{
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      minWidth: "36px",
                                      minHeight: "36px",
                                      padding: "10px",
                                      backgroundColor: "#3B82F615",
                                      borderRadius: "12px",
                                      border: "2px solid #3B82F630",
                                    }}
                                  >
                                    <Icon
                                      source={EyeCheckMarkIcon}
                                      tone="base"
                                    />
                                  </div>
                                </InlineStack>
                                <div style={{ color: "#3B82F6" }}>
                                  <Text
                                    as="p"
                                    variant="headingLg"
                                    fontWeight="bold"
                                  >
                                    {dashboardData.overview.conversion_rate.toFixed(
                                      1,
                                    )}
                                    %
                                  </Text>
                                </div>
                              </BlockStack>
                            </div>
                          </Card>
                        </div>

                        <div
                          style={{
                            transition: "all 0.2s ease-in-out",
                            cursor: "pointer",
                            borderRadius: "8px",
                            overflow: "hidden",
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.transform =
                              "translateY(-2px)";
                            e.currentTarget.style.boxShadow =
                              "0 8px 25px rgba(0,0,0,0.1)";
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.transform = "translateY(0)";
                            e.currentTarget.style.boxShadow = "none";
                          }}
                        >
                          <Card>
                            <div style={{ minHeight: "100px", padding: "4px" }}>
                              <BlockStack gap="300">
                                <InlineStack
                                  align="space-between"
                                  blockAlign="center"
                                >
                                  <BlockStack gap="100">
                                    <Text
                                      as="h4"
                                      variant="headingSm"
                                      tone="subdued"
                                      fontWeight="medium"
                                    >
                                      Recommendations Shown
                                    </Text>
                                  </BlockStack>
                                  <div
                                    style={{
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      minWidth: "36px",
                                      minHeight: "36px",
                                      padding: "10px",
                                      backgroundColor: "#8B5CF615",
                                      borderRadius: "12px",
                                      border: "2px solid #8B5CF630",
                                    }}
                                  >
                                    <Icon source={StarFilledIcon} tone="base" />
                                  </div>
                                </InlineStack>
                                <div style={{ color: "#8B5CF6" }}>
                                  <Text
                                    as="p"
                                    variant="headingLg"
                                    fontWeight="bold"
                                  >
                                    {dashboardData.overview.total_recommendations.toLocaleString()}
                                  </Text>
                                </div>
                              </BlockStack>
                            </div>
                          </Card>
                        </div>
                      </div>
                    </BlockStack>
                  )}

                  <Divider />

                  <InlineStack gap="300">
                    <Button
                      url="/app/widget-config"
                      variant="primary"
                      size="large"
                      icon={SettingsIcon}
                    >
                      {isNewUser ? "Get Started" : "Manage Extensions"}
                    </Button>
                    <Button
                      url="/app/dashboard"
                      variant="secondary"
                      size="large"
                      //icon={AnalyticsMajor}
                    >
                      View Analytics
                    </Button>
                    {!isNewUser && (
                      <Button
                        url="/app/billing"
                        variant="tertiary"
                        size="large"
                        icon={BillIcon}
                      >
                        Billing & Performance
                      </Button>
                    )}
                  </InlineStack>
                </BlockStack>
              </Card>
            </BlockStack>
          </Layout.Section>
        </Layout>

        {/* Quick Actions */}
        <Layout>
          <Layout.Section variant="oneHalf">
            <BlockStack gap="400">
              <div
                style={{
                  padding: "24px",
                  backgroundColor: "#FEF3C7",
                  borderRadius: "12px",
                  border: "1px solid #FCD34D",
                }}
              >
                <div style={{ color: "#92400E" }}>
                  <Text as="h3" variant="headingMd" fontWeight="bold">
                    ⚡ Quick Actions
                  </Text>
                </div>
                <div style={{ marginTop: "8px" }}>
                  <Text as="p" variant="bodyMd" tone="subdued">
                    Get things done quickly with these shortcuts
                  </Text>
                </div>
              </div>

              <Card>
                <BlockStack gap="400">
                  <BlockStack gap="300">
                    <InlineStack align="space-between" blockAlign="center">
                      <InlineStack gap="200" blockAlign="center">
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            minWidth: "32px",
                            minHeight: "32px",
                            padding: "8px",
                            backgroundColor: "#3B82F615",
                            borderRadius: "8px",
                            border: "1px solid #3B82F630",
                          }}
                        >
                          <Icon source={SettingsIcon} tone="base" />
                        </div>
                        <Text as="p" variant="bodyMd" fontWeight="medium">
                          Configure Extensions
                        </Text>
                      </InlineStack>
                      <Button
                        url="/app/widget-config"
                        variant="plain"
                        size="slim"
                        icon={ArrowRightIcon}
                      >
                        Configure
                      </Button>
                    </InlineStack>
                    <InlineStack align="space-between" blockAlign="center">
                      <InlineStack gap="200" blockAlign="center">
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            minWidth: "32px",
                            minHeight: "32px",
                            padding: "8px",
                            backgroundColor: "#8B5CF615",
                            borderRadius: "8px",
                            border: "1px solid #8B5CF630",
                          }}
                        >
                          <Icon source={EyeCheckMarkIcon} tone="base" />
                        </div>
                        <Text as="p" variant="bodyMd" fontWeight="medium">
                          View Performance
                        </Text>
                      </InlineStack>
                      <Button
                        url="/app/dashboard"
                        variant="plain"
                        size="slim"
                        icon={ArrowRightIcon}
                      >
                        View
                      </Button>
                    </InlineStack>
                    {!isNewUser && (
                      <InlineStack align="space-between" blockAlign="center">
                        <InlineStack gap="200" blockAlign="center">
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              minWidth: "32px",
                              minHeight: "32px",
                              padding: "8px",
                              backgroundColor: "#10B98115",
                              borderRadius: "8px",
                              border: "1px solid #10B98130",
                            }}
                          >
                            <Icon source={BillIcon} tone="base" />
                          </div>
                          <Text as="p" variant="bodyMd" fontWeight="medium">
                            Check Billing
                          </Text>
                        </InlineStack>
                        <Button
                          url="/app/billing"
                          variant="plain"
                          size="slim"
                          icon={ArrowRightIcon}
                        >
                          View
                        </Button>
                      </InlineStack>
                    )}
                  </BlockStack>
                </BlockStack>
              </Card>
            </BlockStack>
          </Layout.Section>

          <Layout.Section variant="oneHalf">
            <BlockStack gap="400">
              <div
                style={{
                  padding: "24px",
                  backgroundColor: "#ECFDF5",
                  borderRadius: "12px",
                  border: "1px solid #A7F3D0",
                }}
              >
                <div style={{ color: "#065F46" }}>
                  <Text as="h3" variant="headingMd" fontWeight="bold">
                    ✨ What's New
                  </Text>
                </div>
                <div style={{ marginTop: "8px" }}>
                  <Text as="p" variant="bodyMd" tone="subdued">
                    Latest features and improvements
                  </Text>
                </div>
              </div>

              <Card>
                <BlockStack gap="400">
                  <BlockStack gap="300">
                    <InlineStack gap="200" blockAlign="start">
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          minWidth: "32px",
                          minHeight: "32px",
                          padding: "8px",
                          backgroundColor: "#10B98115",
                          borderRadius: "8px",
                          border: "1px solid #10B98130",
                        }}
                      >
                        <Icon source={CheckCircleIcon} tone="success" />
                      </div>
                      <BlockStack gap="100">
                        <Text as="p" variant="bodyMd" fontWeight="medium">
                          Unified Analytics System
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          Track performance across all extensions with our new
                          unified analytics
                        </Text>
                      </BlockStack>
                    </InlineStack>
                    <InlineStack gap="200" blockAlign="start">
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          minWidth: "32px",
                          minHeight: "32px",
                          padding: "8px",
                          backgroundColor: "#10B98115",
                          borderRadius: "8px",
                          border: "1px solid #10B98130",
                        }}
                      >
                        <Icon source={CheckCircleIcon} tone="success" />
                      </div>
                      <BlockStack gap="100">
                        <Text as="p" variant="bodyMd" fontWeight="medium">
                          Pay-as-Performance Billing
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          Only pay for the revenue you actually generate through
                          recommendations
                        </Text>
                      </BlockStack>
                    </InlineStack>
                    <InlineStack gap="200" blockAlign="start">
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          minWidth: "32px",
                          minHeight: "32px",
                          padding: "8px",
                          backgroundColor: "#10B98115",
                          borderRadius: "8px",
                          border: "1px solid #10B98130",
                        }}
                      >
                        <Icon source={CheckCircleIcon} tone="success" />
                      </div>
                      <BlockStack gap="100">
                        <Text as="p" variant="bodyMd" fontWeight="medium">
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
            </BlockStack>
          </Layout.Section>
        </Layout>

        {/* Help Section */}
        <Layout>
          <Layout.Section>
            <BlockStack gap="400">
              <div
                style={{
                  padding: "24px",
                  backgroundColor: "#F8FAFC",
                  borderRadius: "12px",
                  border: "1px solid #E2E8F0",
                }}
              >
                <div style={{ color: "#1E293B" }}>
                  <Text as="h3" variant="headingMd" fontWeight="bold">
                    🆘 Need Help?
                  </Text>
                </div>
                <div style={{ marginTop: "8px" }}>
                  <Text as="p" variant="bodyMd" tone="subdued">
                    Get the support you need to succeed with BetterBundle
                  </Text>
                </div>
              </div>

              <Card>
                <BlockStack gap="400">
                  <InlineStack gap="400" wrap={false}>
                    <BlockStack gap="200">
                      <Text as="h4" variant="headingSm" fontWeight="medium">
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
                      <Text as="h4" variant="headingSm" fontWeight="medium">
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
                      <Text as="h4" variant="headingSm" fontWeight="medium">
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
            </BlockStack>
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
