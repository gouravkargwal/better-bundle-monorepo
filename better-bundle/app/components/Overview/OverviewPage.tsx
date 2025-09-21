import {
  Page,
  Layout,
  Text,
  Card,
  Button,
  BlockStack,
  InlineStack,
  Icon,
  Badge,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import {
  SettingsIcon,
  BillIcon,
  CashDollarIcon,
  EyeCheckMarkIcon,
  ChartCohortIcon,
} from "@shopify/polaris-icons";
import { getCurrencySymbol } from "app/utils/currency";

interface OverviewPageProps {
  shop: string;
  shopInfo: any;
  billingPlan: any;
  overviewData: any;
  error?: string;
}

export function OverviewPage({
  shop,
  shopInfo,
  billingPlan,
  overviewData,
  error,
}: OverviewPageProps) {
  const shopName = shop.replace(".myshopify.com", "");

  if (error) {
    return (
      <Page>
        <TitleBar title="Overview" />
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

  const formatCurrencyValue = (amount: number, currencyCode: string) => {
    const symbol = getCurrencySymbol(currencyCode);
    const numericAmount = Math.abs(amount);
    return `${symbol}${numericAmount.toFixed(2)}`;
  };

  const getChangeBadge = (change: number | null) => {
    if (change === null) return null;
    const isPositive = change > 0;
    return (
      <Badge tone={isPositive ? "success" : "critical"} size="small">
        {`${isPositive ? "+" : "-"}${change.toFixed(1)}%`}
      </Badge>
    );
  };

  return (
    <Page>
      <TitleBar title="Overview" />
      <BlockStack gap="300">
        {/* Hero Section */}
        <Layout>
          <Layout.Section>
            <BlockStack gap="300">
              {/* Overview Header */}
              <div
                style={{
                  padding: "24px 20px",
                  background:
                    "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                  borderRadius: "16px",
                  color: "white",
                  textAlign: "center",
                  position: "relative",
                  overflow: "hidden",
                  boxShadow:
                    "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                }}
              >
                <div style={{ position: "relative", zIndex: 2 }}>
                  {/* Hero Badge */}
                  <div style={{ marginBottom: "12px" }}>
                    <div
                      style={{
                        display: "inline-block",
                        padding: "6px 12px",
                        backgroundColor: "rgba(255, 255, 255, 0.2)",
                        border: "1px solid rgba(255, 255, 255, 0.3)",
                        color: "white",
                        fontWeight: "600",
                        borderRadius: "6px",
                        fontSize: "12px",
                      }}
                    >
                      📊 Overview Dashboard
                    </div>
                  </div>

                  {/* Main Headline */}
                  <div
                    style={{
                      fontSize: "2rem",
                      lineHeight: "1.2",
                      marginBottom: "8px",
                      background:
                        "linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%)",
                      WebkitBackgroundClip: "text",
                      WebkitTextFillColor: "transparent",
                      backgroundClip: "text",
                      fontWeight: "bold",
                    }}
                  >
                    Welcome back, {shopName}!
                  </div>

                  {/* Subheadline */}
                  <div
                    style={{
                      marginBottom: "12px",
                      maxWidth: "500px",
                      margin: "0 auto 12px",
                    }}
                  >
                    <div
                      style={{
                        color: "rgba(255,255,255,0.95)",
                        lineHeight: "1.4",
                        fontWeight: "500",
                        fontSize: "1rem",
                      }}
                    >
                      Here's how your AI recommendations are performing
                    </div>
                  </div>

                  {/* Enhanced Decorative elements */}
                  <div
                    style={{
                      position: "absolute",
                      top: "-50px",
                      right: "-50px",
                      width: "150px",
                      height: "150px",
                      background:
                        "radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)",
                      borderRadius: "50%",
                      zIndex: 1,
                    }}
                  />
                  <div
                    style={{
                      position: "absolute",
                      bottom: "-40px",
                      left: "-40px",
                      width: "120px",
                      height: "120px",
                      background:
                        "radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 70%)",
                      borderRadius: "50%",
                      zIndex: 1,
                    }}
                  />
                </div>
              </div>

              {/* Key Metrics */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
                  gap: "24px",
                }}
              >
                {/* Revenue Card */}
                <div
                  style={{
                    transition: "all 0.2s ease-in-out",
                    cursor: "pointer",
                    borderRadius: "16px",
                    overflow: "hidden",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = "translateY(-2px)";
                    e.currentTarget.style.boxShadow =
                      "0 8px 25px rgba(0,0,0,0.1)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = "translateY(0)";
                    e.currentTarget.style.boxShadow = "none";
                  }}
                >
                  <Card>
                    <div style={{ padding: "20px" }}>
                      <BlockStack gap="200">
                        <InlineStack align="space-between" blockAlign="center">
                          <BlockStack gap="100">
                            <Text
                              as="h4"
                              variant="headingSm"
                              tone="subdued"
                              fontWeight="medium"
                            >
                              Total Revenue
                            </Text>
                          </BlockStack>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              minWidth: "48px",
                              minHeight: "48px",
                              padding: "12px",
                              backgroundColor: "#10B98115",
                              borderRadius: "12px",
                              border: "2px solid #10B98130",
                            }}
                          >
                            <Icon source={CashDollarIcon} tone="base" />
                          </div>
                        </InlineStack>
                        <div style={{ color: "#10B981" }}>
                          <Text as="p" variant="heading2xl" fontWeight="bold">
                            {formatCurrencyValue(
                              overviewData?.totalRevenue || 0,
                              overviewData?.currency || "USD",
                            )}
                          </Text>
                        </div>
                        {overviewData?.revenueChange !== null && (
                          <div>
                            {getChangeBadge(overviewData.revenueChange)}
                          </div>
                        )}
                      </BlockStack>
                    </div>
                  </Card>
                </div>

                {/* Conversion Rate Card */}
                <div
                  style={{
                    transition: "all 0.2s ease-in-out",
                    cursor: "pointer",
                    borderRadius: "16px",
                    overflow: "hidden",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = "translateY(-2px)";
                    e.currentTarget.style.boxShadow =
                      "0 8px 25px rgba(0,0,0,0.1)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = "translateY(0)";
                    e.currentTarget.style.boxShadow = "none";
                  }}
                >
                  <Card>
                    <div style={{ padding: "20px" }}>
                      <BlockStack gap="200">
                        <InlineStack align="space-between" blockAlign="center">
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
                              minWidth: "48px",
                              minHeight: "48px",
                              padding: "12px",
                              backgroundColor: "#3B82F615",
                              borderRadius: "12px",
                              border: "2px solid #3B82F630",
                            }}
                          >
                            <Icon source={EyeCheckMarkIcon} tone="base" />
                          </div>
                        </InlineStack>
                        <div style={{ color: "#3B82F6" }}>
                          <Text as="p" variant="heading2xl" fontWeight="bold">
                            {(overviewData?.conversionRate || 0).toFixed(1)}%
                          </Text>
                        </div>
                        {overviewData?.conversionRateChange !== null && (
                          <div>
                            {getChangeBadge(overviewData.conversionRateChange)}
                          </div>
                        )}
                      </BlockStack>
                    </div>
                  </Card>
                </div>
              </div>

              {/* Billing Status */}
              {billingPlan && (
                <Card>
                  <div style={{ padding: "20px" }}>
                    <BlockStack gap="300">
                      <div
                        style={{
                          padding: "20px",
                          backgroundColor: "#F0F9FF",
                          borderRadius: "12px",
                          border: "1px solid #BAE6FD",
                        }}
                      >
                        <div style={{ color: "#0C4A6E" }}>
                          <Text as="h3" variant="headingMd" fontWeight="bold">
                            💳 Billing Status
                          </Text>
                        </div>
                        <div style={{ marginTop: "8px" }}>
                          <Text as="p" variant="bodyMd" tone="subdued">
                            {billingPlan.name} • {billingPlan.status}
                          </Text>
                        </div>
                        <div style={{ marginTop: "16px" }}>
                          <Badge tone="success" size="large">
                            Active
                          </Badge>
                        </div>
                      </div>
                    </BlockStack>
                  </div>
                </Card>
              )}

              {/* Help Section & Quick Actions - Side by Side */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
                  gap: "24px",
                }}
              >
                {/* Quick Actions */}
                <Card>
                  <div style={{ padding: "20px" }}>
                    <BlockStack gap="300">
                      <div
                        style={{
                          padding: "20px",
                          backgroundColor: "#FEF3C7",
                          borderRadius: "12px",
                          border: "1px solid #FCD34D",
                        }}
                      >
                        <div style={{ color: "#92400E" }}>
                          <Text as="h3" variant="headingMd" fontWeight="bold">
                            🚀 Quick Actions
                          </Text>
                        </div>
                        <div style={{ marginTop: "8px" }}>
                          <Text as="p" variant="bodyMd" tone="subdued">
                            Get the most out of your AI recommendations
                          </Text>
                        </div>
                      </div>

                      <BlockStack gap="200">
                        <Button
                          url="/app/dashboard"
                          variant="primary"
                          size="large"
                          icon={ChartCohortIcon}
                        >
                          View Full Analytics
                        </Button>
                        <Button
                          url="/app/extensions"
                          variant="secondary"
                          size="large"
                          icon={SettingsIcon}
                        >
                          Manage Extensions
                        </Button>
                        <Button
                          url="/app/billing"
                          variant="tertiary"
                          size="large"
                          icon={BillIcon}
                        >
                          Billing
                        </Button>
                      </BlockStack>
                    </BlockStack>
                  </div>
                </Card>

                {/* Help Section */}
                <Card>
                  <div style={{ padding: "20px" }}>
                    <BlockStack gap="300">
                      <div
                        style={{
                          padding: "20px",
                          backgroundColor: "#F0F9FF",
                          borderRadius: "12px",
                          border: "1px solid #BAE6FD",
                        }}
                      >
                        <div style={{ color: "#0C4A6E" }}>
                          <Text as="h3" variant="headingMd" fontWeight="bold">
                            💡 Need Help?
                          </Text>
                        </div>
                        <div style={{ marginTop: "8px" }}>
                          <Text as="p" variant="bodyMd" tone="subdued">
                            Get started with our guides and support
                          </Text>
                        </div>
                      </div>
                      <BlockStack gap="200">
                        <Button
                          url="mailto:support@betterbundle.com"
                          variant="tertiary"
                          size="large"
                          icon={BillIcon}
                        >
                          Contact Support
                        </Button>
                      </BlockStack>
                    </BlockStack>
                  </div>
                </Card>
              </div>
            </BlockStack>
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
