import { useEffect, useState } from "react";
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
      trackedSales: [],
      summary: {
        totalRevenue: 0,
        totalCommission: 0,
        pendingCommission: 0,
        totalSales: 0,
      },
    });
  }

  // Get commission data
  const trackedSales = await prisma.trackedSale.findMany({
    where: { shopId: shop.id },
    orderBy: { createdAt: "desc" },
    take: 100,
  });

  // Calculate summary
  const totalRevenue = trackedSales.reduce(
    (sum, sale) => sum + sale.revenueGenerated,
    0,
  );
  const totalCommission = trackedSales.reduce(
    (sum, sale) => sum + sale.commissionOwed,
    0,
  );
  const pendingCommission = trackedSales
    .filter((sale) => sale.status === "pending")
    .reduce((sum, sale) => sum + sale.commissionOwed, 0);

  return json({
    trackedSales,
    summary: {
      totalRevenue,
      totalCommission,
      pendingCommission,
      totalSales: trackedSales.length,
    },
  });
};

export default function Commissions() {
  const { trackedSales, summary } = useLoaderData<typeof loader>();
  const [selectedPeriod, setSelectedPeriod] = useState("all");

  const periodOptions = [
    { label: "All Time", value: "all" },
    { label: "This Month", value: "current_month" },
    { label: "Last Month", value: "last_month" },
    { label: "This Quarter", value: "current_quarter" },
  ];

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "pending":
        return <Badge tone="warning">Pending</Badge>;
      case "billed":
        return <Badge tone="success">Billed</Badge>;
      case "disputed":
        return <Badge tone="critical">Disputed</Badge>;
      default:
        return <Badge tone="info">{status}</Badge>;
    }
  };

  return (
    <Page>
      <TitleBar title="Commission Tracking" />

      <Layout>
        {/* Summary Cards */}
        <Layout.Section>
          <BlockStack gap="500">
            <Layout>
              <Layout.Section variant="oneFourth">
                <Card>
                  <BlockStack gap="200">
                    <Text as="h3" variant="headingMd">
                      Total Revenue
                    </Text>
                    <Text as="p" variant="headingLg">
                      ${summary.totalRevenue.toFixed(2)}
                    </Text>
                    <Text as="p" variant="bodyMd">
                      From widget-generated sales
                    </Text>
                  </BlockStack>
                </Card>
              </Layout.Section>

              <Layout.Section variant="oneFourth">
                <Card>
                  <BlockStack gap="200">
                    <Text as="h3" variant="headingMd">
                      Total Commission
                    </Text>
                    <Text as="p" variant="headingLg">
                      ${summary.totalCommission.toFixed(2)}
                    </Text>
                    <Text as="p" variant="bodyMd">
                      5% of widget sales
                    </Text>
                  </BlockStack>
                </Card>
              </Layout.Section>

              <Layout.Section variant="oneFourth">
                <Card>
                  <BlockStack gap="200">
                    <Text as="h3" variant="headingMd">
                      Pending Commission
                    </Text>
                    <Text as="p" variant="headingLg">
                      ${summary.pendingCommission.toFixed(2)}
                    </Text>
                    <Text as="p" variant="bodyMd">
                      Not yet billed
                    </Text>
                  </BlockStack>
                </Card>
              </Layout.Section>

              <Layout.Section variant="oneFourth">
                <Card>
                  <BlockStack gap="200">
                    <Text as="h3" variant="headingMd">
                      Total Sales
                    </Text>
                    <Text as="p" variant="headingLg">
                      {summary.totalSales}
                    </Text>
                    <Text as="p" variant="bodyMd">
                      Widget-generated orders
                    </Text>
                  </BlockStack>
                </Card>
              </Layout.Section>
            </Layout>

            {/* Commission Details */}
            <Card>
              <BlockStack gap="400">
                <InlineStack align="space-between">
                  <Text as="h2" variant="headingMd">
                    Commission Details
                  </Text>
                  <Select
                    label=""
                    labelInline
                    options={periodOptions}
                    value={selectedPeriod}
                    onChange={setSelectedPeriod}
                  />
                </InlineStack>

                {trackedSales.length === 0 ? (
                  <EmptyState
                    heading="No commission data yet"
                    image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                  >
                    <p>
                      Commission data will appear here once customers start
                      purchasing products through your bundle widgets.
                    </p>
                    <Button url="/app" variant="primary">
                      Set Up Bundle Widgets
                    </Button>
                  </EmptyState>
                ) : (
                  <DataTable
                    columnContentTypes={[
                      "text",
                      "numeric",
                      "numeric",
                      "text",
                      "text",
                    ]}
                    headings={[
                      "Order ID",
                      "Revenue",
                      "Commission",
                      "Status",
                      "Date",
                    ]}
                    rows={trackedSales.map((sale) => [
                      sale.shopifyOrderId,
                      `$${sale.revenueGenerated.toFixed(2)}`,
                      `$${sale.commissionOwed.toFixed(2)}`,
                      getStatusBadge(sale.status),
                      new Date(sale.createdAt).toLocaleDateString(),
                    ])}
                  />
                )}
              </BlockStack>
            </Card>
          </BlockStack>
        </Layout.Section>

        {/* Information Panel */}
        <Layout.Section variant="oneThird">
          <BlockStack gap="500">
            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">
                  How Commission Works
                </Text>
                <Text as="p" variant="bodyMd">
                  You only pay commission on sales that are directly generated
                  by our bundle widgets.
                </Text>
                <BlockStack gap="200">
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodyMd">
                      Commission Rate
                    </Text>
                    <Text as="span" variant="bodyMd">
                      5%
                    </Text>
                  </InlineStack>
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodyMd">
                      Billing Cycle
                    </Text>
                    <Text as="span" variant="bodyMd">
                      Monthly
                    </Text>
                  </InlineStack>
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodyMd">
                      Payment Method
                    </Text>
                    <Text as="span" variant="bodyMd">
                      Shopify Billing
                    </Text>
                  </InlineStack>
                </BlockStack>
              </BlockStack>
            </Card>

            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">
                  Commission Status
                </Text>
                <BlockStack gap="200">
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodyMd">
                      Pending
                    </Text>
                    <Badge tone="warning">Not yet billed</Badge>
                  </InlineStack>
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodyMd">
                      Billed
                    </Text>
                    <Badge tone="success">Added to Shopify bill</Badge>
                  </InlineStack>
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodyMd">
                      Disputed
                    </Text>
                    <Badge tone="critical">Under review</Badge>
                  </InlineStack>
                </BlockStack>
              </BlockStack>
            </Card>

            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">
                  Need Help?
                </Text>
                <Text as="p" variant="bodyMd">
                  If you have questions about your commission or billing, please
                  contact our support team.
                </Text>
                <Button url="mailto:support@betterbundle.com" variant="plain">
                  Contact Support
                </Button>
              </BlockStack>
            </Card>
          </BlockStack>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
