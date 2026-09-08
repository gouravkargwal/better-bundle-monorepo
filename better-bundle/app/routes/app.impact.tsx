import { json } from "@remix-run/node";
import type { LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { getImpactDashboard } from "../features/impact/services/impact.service";
import type { ImpactDashboardData } from "../features/impact/types/impact.types";
import {
  Card,
  Text,
  BlockStack,
  InlineStack,
  Badge,
  Tabs,
  Page,
  Banner,
} from "@shopify/polaris";
import { useState } from "react";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const url = new URL(request.url);
  const startDate = url.searchParams.get("startDate") || undefined;
  const endDate = url.searchParams.get("endDate") || undefined;

  const data = await getImpactDashboard(
    session.shop,
    startDate,
    endDate,
  );

  return json(data);
};

export default function ImpactDashboard() {
  const data = useLoaderData<ImpactDashboardData>();
  const [selectedTab, setSelectedTab] = useState(0);

  const tabs = [
    { id: "impact", content: "Impact" },
    { id: "funnel", content: "Funnel" },
    { id: "offers", content: "Offers" },
  ];

  return (
    <Page title="Impact Dashboard">
      <BlockStack gap="400">
        {/* Methodology Banner */}
        <Banner tone="info">
          <Text as="p" variant="bodySm">
            <strong>Causal measurement:</strong> {data.holdoutConfig.percent}% of
            eligible checkouts see no offer as a control group. Revenue lift is
            calculated against this baseline, not attributed revenue.{" "}
            {data.summary.isSignificant
              ? `p=${data.summary.pValue.toFixed(3)} — statistically significant.`
              : "Collecting data for a confident read (need 100+ control orders)."}
          </Text>
        </Banner>

        <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
          {/* Tab 1: Impact */}
          {selectedTab === 0 && <ImpactTab data={data} />}
          {/* Tab 2: Funnel */}
          {selectedTab === 1 && <FunnelTab data={data} />}
          {/* Tab 3: Offers */}
          {selectedTab === 2 && <OffersTab data={data} />}
        </Tabs>
      </BlockStack>
    </Page>
  );
}

function ImpactTab({ data }: { data: ImpactDashboardData }) {
  const { summary, holdoutConfig } = data;
  return (
    <BlockStack gap="400">
      {/* Hero Metric */}
      <Card>
        <BlockStack gap="300">
          <InlineStack align="space-between" blockAlign="center">
            <Text as="h2" variant="headingXl" fontWeight="bold">
              ${summary.incrementalRevenue.toLocaleString()}
            </Text>
            <Badge tone={summary.isSignificant ? "success" : "warning"}>
              {summary.status === "sentinel"
                ? "Monitoring"
                : summary.isSignificant
                  ? "Significant"
                  : "Collecting data"}
            </Badge>
          </InlineStack>
          <Text as="p" variant="headingMd">
            incremental revenue (95% CI: $
            {summary.incrementalRevenueLower.toLocaleString()} – $
            {summary.incrementalRevenueUpper.toLocaleString()})
          </Text>
          <Text as="p" variant="bodyLg">
            +{summary.aovLiftPercent.toFixed(1)}% AOV lift vs. control group
          </Text>
        </BlockStack>
      </Card>

      {/* Quick Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "16px" }}>
        <Card>
          <BlockStack gap="100">
            <Text as="p" variant="bodySm" tone="subdued">
              Treatment Impressions
            </Text>
            <Text as="p" variant="headingXl">
              {summary.treatmentOrders.toLocaleString()}
            </Text>
          </BlockStack>
        </Card>
        <Card>
          <BlockStack gap="100">
            <Text as="p" variant="bodySm" tone="subdued">
              Accepts
            </Text>
            <Text as="p" variant="headingXl">
              {summary.totalAccepts.toLocaleString()}
            </Text>
          </BlockStack>
        </Card>
        <Card>
          <BlockStack gap="100">
            <Text as="p" variant="bodySm" tone="subdued">
              Control Sessions
            </Text>
            <Text as="p" variant="headingXl">
              {summary.controlOrders.toLocaleString()}
            </Text>
          </BlockStack>
        </Card>
      </div>

      {/* Holdout Config */}
      <Card>
        <BlockStack gap="200">
          <Text as="h3" variant="headingMd">
            Holdout Configuration
          </Text>
          <InlineStack gap="200" blockAlign="center">
            <Badge tone={holdoutConfig.enabled ? "success" : "critical"}>
              {holdoutConfig.enabled ? "Active" : "Disabled"}
            </Badge>
            <Text as="p" variant="bodyMd">
              {holdoutConfig.percent}% of traffic held out as control
            </Text>
          </InlineStack>
        </BlockStack>
      </Card>
    </BlockStack>
  );
}

function FunnelTab({ data }: { data: ImpactDashboardData }) {
  if (data.funnels.length === 0) {
    return (
      <Card>
        <Text as="p" variant="bodyMd" tone="subdued">
          No funnel data yet. Offers need to be shown before the funnel appears.
        </Text>
      </Card>
    );
  }

  return (
    <BlockStack gap="300">
      {data.funnels.map((row) => (
        <Card key={row.surface}>
          <BlockStack gap="200">
            <Text as="h3" variant="headingMd">
              {row.surface === "apollo" ? "Apollo (Post-Purchase)" : "Mercury (Checkout)"}
            </Text>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(4, 1fr)",
                gap: "16px",
              }}
            >
              <div>
                <Text as="p" variant="bodySm" tone="subdued">
                  Impressions
                </Text>
                <Text as="p" variant="headingLg">
                  {row.impressions.toLocaleString()}
                </Text>
              </div>
              <div>
                <Text as="p" variant="bodySm" tone="subdued">
                  Accepted
                </Text>
                <Text as="p" variant="headingLg">
                  {row.accepts.toLocaleString()}
                </Text>
              </div>
              <div>
                <Text as="p" variant="bodySm" tone="subdued">
                  Revenue
                </Text>
                <Text as="p" variant="headingLg">
                  ${row.revenue.toLocaleString()}
                </Text>
              </div>
              <div>
                <Text as="p" variant="bodySm" tone="subdued">
                  Conv. Rate
                </Text>
                <Text as="p" variant="headingLg">
                  {row.conversionRate.toFixed(1)}%
                </Text>
              </div>
            </div>
          </BlockStack>
        </Card>
      ))}
    </BlockStack>
  );
}

function OffersTab({ data }: { data: ImpactDashboardData }) {
  if (data.topOffers.length === 0) {
    return (
      <Card>
        <Text as="p" variant="bodyMd" tone="subdued">
          No offer data yet. Accepted offers will appear here.
        </Text>
      </Card>
    );
  }

  return (
    <BlockStack gap="400">
      <Card>
        <BlockStack gap="200">
          <Text as="h3" variant="headingMd">
            Top Performing Offers
          </Text>
          {data.topOffers.map((offer, idx) => (
            <div
              key={idx}
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
                gap: "12px",
                padding: "8px 0",
                borderBottom: "1px solid #e5e7eb",
              }}
            >
              <Text as="p" variant="bodyMd" fontWeight="bold">
                {offer.productTitleA || offer.productIdA}
              </Text>
              <Text as="p" variant="bodyMd">
                {offer.impressions} shown
              </Text>
              <Text as="p" variant="bodyMd">
                {offer.accepts} accepted
              </Text>
              <Text as="p" variant="bodyMd">
                ${offer.revenue.toLocaleString()}
              </Text>
              <Text as="p" variant="bodyMd">
                {offer.conversionRate.toFixed(1)}%
              </Text>
            </div>
          ))}
        </BlockStack>
      </Card>

      <Card>
        <BlockStack gap="200">
          <Text as="h3" variant="headingMd" tone="critical">
            Worst Performing Offers
          </Text>
          {data.worstOffers.map((offer, idx) => (
            <div
              key={idx}
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
                gap: "12px",
                padding: "8px 0",
                borderBottom: "1px solid #e5e7eb",
              }}
            >
              <Text as="p" variant="bodyMd">
                {offer.productTitleA || offer.productIdA}
              </Text>
              <Text as="p" variant="bodyMd">
                {offer.impressions} shown
              </Text>
              <Text as="p" variant="bodyMd">
                {offer.accepts} accepted
              </Text>
              <Text as="p" variant="bodyMd">
                ${offer.revenue.toLocaleString()}
              </Text>
              <Text as="p" variant="bodyMd">
                {offer.conversionRate.toFixed(1)}%
              </Text>
            </div>
          ))}
        </BlockStack>
      </Card>
    </BlockStack>
  );
}
