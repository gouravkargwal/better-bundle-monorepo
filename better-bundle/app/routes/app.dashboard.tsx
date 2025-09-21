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
} from "@shopify/polaris";
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
        <BlockStack gap="500">
          <div
            style={{
              padding: "48px",
              textAlign: "center",
              backgroundColor: "#F8FAFC",
              borderRadius: "16px",
              border: "1px solid #E2E8F0",
            }}
          >
            <Spinner size="large" />
            <div style={{ marginTop: "24px" }}>
              <BlockStack gap="300">
                <Text as="h3" variant="headingMd" fontWeight="bold">
                  Loading your analytics...
                </Text>
                <Text as="p" variant="bodyMd" tone="subdued">
                  We're gathering your extension performance data
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
          <BlockStack gap="500">
            <RevenueKPICards
              data={dashboardData.overview}
              attributedMetrics={dashboardData.attributedMetrics}
            />
          </BlockStack>
        );
      case 1: // Performance
        return (
          <BlockStack gap="500">
            <PerformanceKPICards data={dashboardData.overview} />
          </BlockStack>
        );
      case 2: // Top Products
        return (
          <BlockStack gap="500">
            <TopProductsTable data={dashboardData.topProducts} />
          </BlockStack>
        );
      case 3: // Recent Activity
        return (
          <BlockStack gap="500">
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
      <BlockStack gap="400">
        <Tabs tabs={tabs} selected={selectedTab} onSelect={handleTabChange}>
          {renderTabContent()}
        </Tabs>
      </BlockStack>
    </Page>
  );
}
