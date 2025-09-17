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
import { getExtensionStatus } from "../services/extension.service";
import { KPICards } from "../components/dashboard/KPICards";
import { ContextPerformance } from "../components/dashboard/ContextPerformance";
import { TopProductsTable } from "../components/dashboard/TopProductsTable";
import { RecentActivity } from "../components/dashboard/RecentActivity";
import { ExtensionPerformance } from "../components/dashboard/ExtensionPerformance";
import { PerformanceCharts } from "../components/dashboard/PerformanceCharts";
import { StatusOverview } from "../components/dashboard/StatusOverview";
import { QuickActions } from "../components/dashboard/QuickActions";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    const [dashboardData, extensionStatus] = await Promise.all([
      getDashboardOverview(session.shop),
      getExtensionStatus(session.shop),
    ]);

    return {
      dashboardData,
      extensionStatus,
      shop: session.shop,
    };
  } catch (error) {
    console.error("Dashboard loader error:", error);
    return {
      dashboardData: null,
      extensionStatus: null,
      shop: session.shop,
      error: "Failed to load dashboard data",
    };
  }
};

export default function Dashboard() {
  const { dashboardData, extensionStatus, shop, error } =
    useLoaderData<typeof loader>();

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

          {/* Quick Actions */}
          <Layout.Section variant="oneThird">
            <QuickActions />
          </Layout.Section>

          {/* System Status */}
          <Layout.Section variant="twoThirds">
            <StatusOverview
              data={{
                system_health: extensionStatus?.overallStatus || "critical",
                extensions_status: extensionStatus
                  ? Object.values(extensionStatus.extensions).map((ext) => ({
                      name: ext.name,
                      status: ext.status,
                      last_activity:
                        ext.last_activity || new Date().toISOString(),
                    }))
                  : [],
                data_sync_status: {
                  last_sync: new Date().toISOString(),
                  sync_frequency: "Real-time",
                  status: "synced",
                },
                performance_metrics: {
                  response_time: 150,
                  uptime: 99.9,
                  error_rate: 0.1,
                },
              }}
            />
          </Layout.Section>

          {/* Performance Charts */}
          <Layout.Section>
            <PerformanceCharts
              data={{
                revenue_trend: [
                  { date: "2024-01-01", value: 1200 },
                  { date: "2024-01-02", value: 1350 },
                  { date: "2024-01-03", value: 1100 },
                  { date: "2024-01-04", value: 1450 },
                  { date: "2024-01-05", value: 1600 },
                  { date: "2024-01-06", value: 1400 },
                  { date: "2024-01-07", value: 1700 },
                ],
                conversion_trend: [
                  { date: "2024-01-01", value: 3.2 },
                  { date: "2024-01-02", value: 3.5 },
                  { date: "2024-01-03", value: 2.8 },
                  { date: "2024-01-04", value: 4.1 },
                  { date: "2024-01-05", value: 4.3 },
                  { date: "2024-01-06", value: 3.9 },
                  { date: "2024-01-07", value: 4.5 },
                ],
                top_performing_extensions: [
                  { name: "Atlas", revenue: 850, conversion_rate: 4.2 },
                  { name: "Phoenix", revenue: 620, conversion_rate: 3.8 },
                  { name: "Venus", revenue: 480, conversion_rate: 3.5 },
                  { name: "Apollo", revenue: 320, conversion_rate: 3.1 },
                ],
              }}
              currency_code={dashboardData.overview.currency_code}
            />
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
