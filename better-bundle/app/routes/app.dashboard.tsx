import type { LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Page,
  Layout,
  Text,
  BlockStack,
  Spinner,
  Banner,
  Tabs,
  Icon,
} from "@shopify/polaris";
import { ChartCohortIcon } from "@shopify/polaris-icons";
import { TitleBar } from "@shopify/app-bridge-react";
import { useState, useCallback } from "react";
import { authenticate } from "../shopify.server";
import { getDashboardOverview } from "../services/dashboard.service";
import {
  RevenueKPICards,
  PerformanceKPICards,
} from "../components/Dashboard/KPICards";
import { TopProductsTable } from "../components/Dashboard/TopProductsTable";
import { RecentActivity } from "../components/Dashboard/RecentActivity";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    const dashboardData = await getDashboardOverview(session.shop);

    return {
      dashboardData,
      shop: session.shop,
    };
  } catch (error) {
    console.error("Dashboard loader error:", error);
    return {
      dashboardData: null,
      shop: session.shop,
      error: "Failed to load dashboard data",
    };
  }
};

export default function Dashboard() {
  const loaderData = useLoaderData<typeof loader>();
  const { dashboardData } = loaderData;
  const error = "error" in loaderData ? loaderData.error : undefined;
  const [selectedTab, setSelectedTab] = useState(0);

  const handleTabChange = useCallback((selectedTabIndex: number) => {
    setSelectedTab(selectedTabIndex);
  }, []);

  if (error) {
    return (
      <Page>
        <TitleBar title="Analytics Dashboard" />
        <Layout>
          <Layout.Section>
            <Banner tone="critical" title="Error loading dashboard">
              <p>{error}</p>
            </Banner>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  if (!dashboardData) {
    return (
      <Page>
        <TitleBar title="Analytics Dashboard" />
        <BlockStack gap="300">
          <div
            style={{
              padding: "40px 32px",
              textAlign: "center",
              background: "linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%)",
              borderRadius: "16px",
              border: "1px solid #E2E8F0",
            }}
          >
            <div
              style={{
                display: "inline-block",
                padding: "12px",
                backgroundColor: "#3B82F615",
                borderRadius: "12px",
                marginBottom: "16px",
              }}
            >
              <Icon source={ChartCohortIcon} tone="base" />
            </div>
            <Spinner size="large" />
            <div style={{ marginTop: "24px" }}>
              <BlockStack gap="300">
                <div style={{ color: "#1E293B" }}>
                  <Text as="h3" variant="headingLg" fontWeight="bold">
                    📊 Loading your analytics...
                  </Text>
                </div>
                <Text as="p" variant="bodyLg" tone="subdued">
                  We're gathering your extension performance data and generating
                  insights
                </Text>
              </BlockStack>
            </div>
          </div>
        </BlockStack>
      </Page>
    );
  }

  const tabs = [
    {
      id: "revenue",
      content: "💰 Revenue",
      panelID: "revenue-panel",
    },
    {
      id: "performance",
      content: "📊 Performance",
      panelID: "performance-panel",
    },
    {
      id: "products",
      content: "🏆 Top Products",
      panelID: "products-panel",
    },
    {
      id: "activity",
      content: "⚡ Recent Activity",
      panelID: "activity-panel",
    },
  ];

  const renderTabContent = () => {
    switch (selectedTab) {
      case 0: // Revenue
        return (
          <BlockStack gap="300">
            <RevenueKPICards
              data={dashboardData.overview}
              attributedMetrics={dashboardData.attributedMetrics}
            />
          </BlockStack>
        );
      case 1: // Performance
        return (
          <BlockStack gap="300">
            <PerformanceKPICards data={dashboardData.overview} />
          </BlockStack>
        );
      case 2: // Top Products
        return (
          <BlockStack gap="300">
            <TopProductsTable data={dashboardData.topProducts} />
          </BlockStack>
        );
      case 3: // Recent Activity
        return (
          <BlockStack gap="300">
            <RecentActivity data={dashboardData.recentActivity} />
          </BlockStack>
        );
      default:
        return null;
    }
  };

  return (
    <Page>
      <TitleBar title="Analytics Dashboard" />
      <BlockStack gap="300">
        {/* Hero Section */}
        <div
          style={{
            padding: "24px 20px",
            background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
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
                📊 Analytics Dashboard
              </div>
            </div>

            {/* Main Headline */}
            <div
              style={{
                fontSize: "2rem",
                lineHeight: "1.2",
                marginBottom: "8px",
                background: "linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
                fontWeight: "bold",
              }}
            >
              Performance Analytics
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
                Track your AI recommendations performance and revenue impact
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

        <Tabs tabs={tabs} selected={selectedTab} onSelect={handleTabChange}>
          {renderTabContent()}
        </Tabs>
      </BlockStack>
    </Page>
  );
}
