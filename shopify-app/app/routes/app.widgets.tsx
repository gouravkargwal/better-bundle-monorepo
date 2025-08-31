import { useState } from "react";
import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Page,
  Layout,
  Text,
  Card,
  BlockStack,
  InlineStack,
  Badge,
  DataTable,
  EmptyState,
  Button,
  Select,
  ProgressBar,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shopId = session.shop;

  // Get shop from database first
  const shop = await prisma.shop.findUnique({
    where: { shopDomain: shopId },
    select: { id: true },
  });

  if (!shop) {
    return json({
      widgetEvents: [],
      metrics: {
        totalViews: 0,
        totalClicks: 0,
        totalAddToCart: 0,
        totalPurchases: 0,
        clickThroughRate: 0,
        conversionRate: 0,
        addToCartRate: 0,
      },
      bundlePerformance: {},
    });
  }

  // Get widget event data
  const widgetEvents = await prisma.widgetEvent.findMany({
    where: { shopId: shop.id },
    orderBy: { timestamp: "desc" },
    take: 1000,
  });

  // Calculate metrics
  const totalViews = widgetEvents.filter((e) => e.action === "view").length;
  const totalClicks = widgetEvents.filter((e) => e.action === "click").length;
  const totalAddToCart = widgetEvents.filter(
    (e) => e.action === "add_to_cart",
  ).length;
  const totalPurchases = widgetEvents.filter(
    (e) => e.action === "purchase",
  ).length;

  const clickThroughRate =
    totalViews > 0 ? (totalClicks / totalViews) * 100 : 0;
  const conversionRate =
    totalClicks > 0 ? (totalPurchases / totalClicks) * 100 : 0;
  const addToCartRate =
    totalClicks > 0 ? (totalAddToCart / totalClicks) * 100 : 0;

  // Get top performing bundles
  const bundlePerformance = widgetEvents
    .filter((e) => e.bundleId)
    .reduce(
      (acc, event) => {
        if (!acc[event.bundleId!]) {
          acc[event.bundleId!] = { views: 0, clicks: 0, purchases: 0 };
        }
        acc[event.bundleId!][event.action as keyof (typeof acc)[string]]++;
        return acc;
      },
      {} as Record<
        string,
        { views: number; clicks: number; purchases: number }
      >,
    );

  return json({
    widgetEvents,
    metrics: {
      totalViews,
      totalClicks,
      totalAddToCart,
      totalPurchases,
      clickThroughRate,
      conversionRate,
      addToCartRate,
    },
    bundlePerformance,
  });
};

export default function Widgets() {
  const { widgetEvents, metrics, bundlePerformance } =
    useLoaderData<typeof loader>();
  const [selectedPeriod, setSelectedPeriod] = useState("7d");

  const periodOptions = [
    { label: "Last 7 Days", value: "7d" },
    { label: "Last 30 Days", value: "30d" },
    { label: "Last 90 Days", value: "90d" },
    { label: "All Time", value: "all" },
  ];

  const getActionBadge = (action: string) => {
    switch (action) {
      case "view":
        return <Badge tone="info">View</Badge>;
      case "click":
        return <Badge tone="success">Click</Badge>;
      case "add_to_cart":
        return <Badge tone="warning">Add to Cart</Badge>;
      case "purchase":
        return <Badge tone="success">Purchase</Badge>;
      default:
        return <Badge tone="info">{action}</Badge>;
    }
  };

  return (
    <Page>
      <TitleBar title="Widget Analytics" />

      <Layout>
        {/* Metrics Overview */}
        <Layout.Section>
          <BlockStack gap="500">
            <Layout>
              <Layout.Section variant="oneFourth">
                <Card>
                  <BlockStack gap="200">
                    <Text as="h3" variant="headingMd">
                      Widget Views
                    </Text>
                    <Text as="p" variant="headingLg">
                      {metrics.totalViews.toLocaleString()}
                    </Text>
                    <Text as="p" variant="bodyMd">
                      Total widget impressions
                    </Text>
                  </BlockStack>
                </Card>
              </Layout.Section>

              <Layout.Section variant="oneFourth">
                <Card>
                  <BlockStack gap="200">
                    <Text as="h3" variant="headingMd">
                      Click-Through Rate
                    </Text>
                    <Text as="p" variant="headingLg">
                      {metrics.clickThroughRate.toFixed(1)}%
                    </Text>
                    <Text as="p" variant="bodyMd">
                      Clicks per view
                    </Text>
                    <ProgressBar
                      progress={metrics.clickThroughRate}
                      size="small"
                    />
                  </BlockStack>
                </Card>
              </Layout.Section>

              <Layout.Section variant="oneFourth">
                <Card>
                  <BlockStack gap="200">
                    <Text as="h3" variant="headingMd">
                      Add to Cart Rate
                    </Text>
                    <Text as="p" variant="headingLg">
                      {metrics.addToCartRate.toFixed(1)}%
                    </Text>
                    <Text as="p" variant="bodyMd">
                      Add to cart per click
                    </Text>
                    <ProgressBar
                      progress={metrics.addToCartRate}
                      size="small"
                    />
                  </BlockStack>
                </Card>
              </Layout.Section>

              <Layout.Section variant="oneFourth">
                <Card>
                  <BlockStack gap="200">
                    <Text as="h3" variant="headingMd">
                      Conversion Rate
                    </Text>
                    <Text as="p" variant="headingLg">
                      {metrics.conversionRate.toFixed(1)}%
                    </Text>
                    <Text as="p" variant="bodyMd">
                      Purchases per click
                    </Text>
                    <ProgressBar
                      progress={metrics.conversionRate}
                      size="small"
                    />
                  </BlockStack>
                </Card>
              </Layout.Section>
            </Layout>

            {/* Widget Events */}
            <Card>
              <BlockStack gap="400">
                <InlineStack align="space-between">
                  <Text as="h2" variant="headingMd">
                    Recent Widget Events
                  </Text>
                  <Select
                    label=""
                    labelInline
                    options={periodOptions}
                    value={selectedPeriod}
                    onChange={setSelectedPeriod}
                  />
                </InlineStack>

                {widgetEvents.length === 0 ? (
                  <EmptyState
                    heading="No widget data yet"
                    image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                  >
                    <p>
                      Widget analytics will appear here once customers start
                      interacting with your bundle widgets.
                    </p>
                    <Button url="/app" variant="primary">
                      Set Up Bundle Widgets
                    </Button>
                  </EmptyState>
                ) : (
                  <DataTable
                    columnContentTypes={["text", "text", "text", "text"]}
                    headings={["Action", "Bundle ID", "Products", "Timestamp"]}
                    rows={widgetEvents
                      .slice(0, 20)
                      .map((event) => [
                        getActionBadge(event.action),
                        event.bundleId || "N/A",
                        event.productIds.join(", "),
                        new Date(event.timestamp).toLocaleString(),
                      ])}
                  />
                )}
              </BlockStack>
            </Card>
          </BlockStack>
        </Layout.Section>

        {/* Bundle Performance */}
        <Layout.Section variant="oneThird">
          <BlockStack gap="500">
            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">
                  Bundle Performance
                </Text>
                <Text as="p" variant="bodyMd">
                  How individual bundles are performing with customers.
                </Text>
              </BlockStack>
            </Card>

            {Object.keys(bundlePerformance).length === 0 ? (
              <Card>
                <BlockStack gap="200">
                  <Text as="h3" variant="headingMd">
                    No Bundle Data
                  </Text>
                  <Text as="p" variant="bodyMd">
                    Bundle performance data will appear here once customers
                    interact with your bundles.
                  </Text>
                </BlockStack>
              </Card>
            ) : (
              Object.entries(bundlePerformance).map(
                ([bundleId, performance]) => (
                  <Card key={bundleId}>
                    <BlockStack gap="200">
                      <Text as="h3" variant="headingMd">
                        Bundle {bundleId.slice(-8)}
                      </Text>
                      <BlockStack gap="200">
                        <InlineStack align="space-between">
                          <Text as="span" variant="bodyMd">
                            Views
                          </Text>
                          <Text as="span" variant="bodyMd">
                            {performance.views}
                          </Text>
                        </InlineStack>
                        <InlineStack align="space-between">
                          <Text as="span" variant="bodyMd">
                            Clicks
                          </Text>
                          <Text as="span" variant="bodyMd">
                            {performance.clicks}
                          </Text>
                        </InlineStack>
                        <InlineStack align="space-between">
                          <Text as="span" variant="bodyMd">
                            Purchases
                          </Text>
                          <Text as="span" variant="bodyMd">
                            {performance.purchases}
                          </Text>
                        </InlineStack>
                        <ProgressBar
                          progress={
                            performance.views > 0
                              ? (performance.purchases / performance.views) *
                                100
                              : 0
                          }
                          size="small"
                        />
                      </BlockStack>
                    </BlockStack>
                  </Card>
                ),
              )
            )}

            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">
                  Widget Optimization Tips
                </Text>
                <Text as="p" variant="bodyMd">
                  Improve your widget performance with these tips:
                </Text>
                <BlockStack gap="200">
                  <Text as="p" variant="bodyMd">
                    • Place widgets on high-traffic product pages
                  </Text>
                  <Text as="p" variant="bodyMd">
                    • Test different bundle combinations
                  </Text>
                  <Text as="p" variant="bodyMd">
                    • Monitor conversion rates regularly
                  </Text>
                  <Text as="p" variant="bodyMd">
                    • Adjust bundle pricing for better conversions
                  </Text>
                </BlockStack>
              </BlockStack>
            </Card>
          </BlockStack>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
