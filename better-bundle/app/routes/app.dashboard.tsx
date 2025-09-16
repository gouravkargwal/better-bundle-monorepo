import type { LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Page,
  Layout,
  Text,
  Card,
  BlockStack,
  Spinner,
  Banner,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { getDashboardOverview } from "../services/dashboard.service";
import { KPICards } from "../components/dashboard/KPICards";
import { ContextPerformance } from "../components/dashboard/ContextPerformance";
import { TopProductsTable } from "../components/dashboard/TopProductsTable";
import { RecentActivity } from "../components/dashboard/RecentActivity";
import { ExtensionPerformance } from "../components/dashboard/ExtensionPerformance";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    const dashboardData = await getDashboardOverview(session.shop);
    return { dashboardData, shop: session.shop };
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
  const { dashboardData, shop, error } = useLoaderData<typeof loader>();

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
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack align="center" gap="400">
                <Spinner size="large" />
                <Text as="p" variant="bodyMd">
                  Loading dashboard data...
                </Text>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  return (
    <Page>
      <TitleBar title="Analytics Dashboard" />
      <BlockStack gap="500">
        <Layout>
          {/* KPI Cards */}
          <Layout.Section>
            <KPICards data={dashboardData.overview} />
          </Layout.Section>

          {/* Extension Performance */}
          <Layout.Section>
            <ExtensionPerformance data={dashboardData.extensionPerformance} />
          </Layout.Section>

          {/* Context Performance */}
          <Layout.Section>
            <ContextPerformance data={dashboardData.contextPerformance} />
          </Layout.Section>

          {/* Top Products and Recent Activity */}
          <Layout.Section variant="oneHalf">
            <TopProductsTable data={dashboardData.topProducts} />
          </Layout.Section>

          <Layout.Section variant="oneHalf">
            <RecentActivity data={dashboardData.recentActivity} />
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
