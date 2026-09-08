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
import { TitleBar } from "@shopify/app-bridge-react";
import { HeroHeader } from "../components/UI/HeroHeader";
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
    { id: "impact", content: "📈 Impact" },
    { id: "funnel", content: "🔄 Funnel" },
    { id: "offers", content: "🏆 Offers" },
  ];

  return (
    <Page>
      <TitleBar title="Impact" />
      <BlockStack gap="300">
        <HeroHeader
          title="Revenue your recommendations actually drive"
          subtitle="Causal measurement against a control group — not attributed numbers. See lift, confidence, and what to do next."
          variant="gradient"
          align="left"
          textTreatment="inverted"
        />

        <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab} fitted>
          <div style={{ padding: "16px 0" }}>
            <BlockStack gap="500">
              {/* Methodology Banner */}
              <Banner tone="info">
                <Text as="p" variant="bodySm">
                  <strong>Causal measurement:</strong>{" "}
                  {data.holdoutConfig.percent}% of eligible checkouts see no
                  offer as a control group. Revenue lift is calculated against
                  this baseline, not attributed revenue.{" "}
                  {data.summary.isSignificant
                    ? `p=${data.summary.pValue.toFixed(3)} — statistically significant.`
                    : "Collecting data for a confident read (need 100+ control orders)."}
                </Text>
              </Banner>

              {/* Tab 1: Impact */}
              {selectedTab === 0 && <ImpactTab data={data} />}
              {/* Tab 2: Funnel */}
              {selectedTab === 1 && <FunnelTab data={data} />}
              {/* Tab 3: Offers */}
              {selectedTab === 2 && <OffersTab data={data} />}
            </BlockStack>
          </div>
        </Tabs>
      </BlockStack>
    </Page>
  );
}

function ImpactTab({ data }: { data: ImpactDashboardData }) {
  const { summary, holdoutConfig } = data;
  const isSignificant = summary.isSignificant;

  return (
    <BlockStack gap="500">
      {/* Hero Metric Card */}
      <Card>
        <div style={{ padding: "24px" }}>
          <BlockStack gap="400">
            <InlineStack align="space-between" blockAlign="center">
              <BlockStack gap="100">
                <Text variant="headingMd" as="h3">
                  💰 Incremental Revenue
                </Text>
                <Text as="p" tone="subdued">
                  Measured against the control group · 95% confidence interval
                </Text>
              </BlockStack>
              <Badge
                tone={isSignificant ? "success" : "warning"}
                size="large"
              >
                {summary.status === "sentinel"
                  ? "Monitoring"
                  : isSignificant
                    ? "Significant"
                    : "Collecting data"}
              </Badge>
            </InlineStack>

            <div
              style={{
                padding: "24px",
                backgroundColor: isSignificant ? "#F0FDF4" : "#FEF3C7",
                borderRadius: "12px",
                border: `2px solid ${isSignificant ? "#22C55E" : "#F59E0B"}`,
              }}
            >
              <BlockStack gap="200">
                <Text as="h3" variant="heading2xl" fontWeight="bold">
                  ${summary.incrementalRevenue.toLocaleString()}
                </Text>
                <InlineStack gap="200" wrap>
                  <Text as="p" variant="bodyMd" fontWeight="medium">
                    +{summary.aovLiftPercent.toFixed(1)}% AOV lift vs. control
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    95% CI: ${summary.incrementalRevenueLower.toLocaleString()} –
                    ${summary.incrementalRevenueUpper.toLocaleString()}
                  </Text>
                </InlineStack>
              </BlockStack>
            </div>
          </BlockStack>
        </div>
      </Card>

      {/* Insights */}
      {data.insights.length > 0 && (
        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="300">
              <Text variant="headingMd" as="h3">
                💡 What to do next
              </Text>
              <BlockStack gap="200">
                {data.insights.map((insight, i) => {
                  const style = INSIGHT_STYLES[insight.tone];
                  return (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        gap: "10px",
                        alignItems: "flex-start",
                        padding: "12px",
                        backgroundColor: style.bg,
                        borderRadius: "8px",
                        border: `1px solid ${style.border}`,
                      }}
                    >
                      <span style={{ flexShrink: 0 }}>{style.emoji}</span>
                      <Text as="p" variant="bodyMd">
                        {insight.text}
                      </Text>
                    </div>
                  );
                })}
              </BlockStack>
            </BlockStack>
          </div>
        </Card>
      )}

      {/* Quick Stats */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "16px",
        }}
      >
        <Card>
          <div style={{ padding: "20px" }}>
            <BlockStack gap="100">
              <Text as="p" variant="bodySm" tone="subdued">
                👀 Treatment Impressions
              </Text>
              <Text as="h3" variant="headingXl" fontWeight="bold">
                {summary.treatmentOrders.toLocaleString()}
              </Text>
            </BlockStack>
          </div>
        </Card>
        <Card>
          <div style={{ padding: "20px" }}>
            <BlockStack gap="100">
              <Text as="p" variant="bodySm" tone="subdued">
                ✅ Accepts
              </Text>
              <Text as="h3" variant="headingXl" fontWeight="bold">
                {summary.totalAccepts.toLocaleString()}
              </Text>
            </BlockStack>
          </div>
        </Card>
        <Card>
          <div style={{ padding: "20px" }}>
            <BlockStack gap="100">
              <Text as="p" variant="bodySm" tone="subdued">
                🎛️ Control Sessions
              </Text>
              <Text as="h3" variant="headingXl" fontWeight="bold">
                {summary.controlOrders.toLocaleString()}
              </Text>
            </BlockStack>
          </div>
        </Card>
      </div>

      {/* Revenue over time */}
      <TrendsCard
        trends={data.trends}
        symbol={data.currencyCode === "USD" ? "$" : ""}
      />

      {/* Holdout Config */}
      <Card>
        <div style={{ padding: "24px" }}>
          <BlockStack gap="300">
            <Text as="h3" variant="headingMd" fontWeight="semibold">
              🧪 Holdout Configuration
            </Text>
            <div
              style={{
                padding: "16px",
                backgroundColor: holdoutConfig.enabled ? "#F0FDF4" : "#FEF2F2",
                borderRadius: "12px",
                border: `1px solid ${holdoutConfig.enabled ? "#BBF7D0" : "#FECACA"}`,
              }}
            >
              <InlineStack align="space-between" blockAlign="center">
                <Text as="p" variant="bodyMd">
                  {holdoutConfig.percent}% of traffic held out as control group
                </Text>
                <Badge tone={holdoutConfig.enabled ? "success" : "critical"}>
                  {holdoutConfig.enabled ? "Active" : "Disabled"}
                </Badge>
              </InlineStack>
            </div>
          </BlockStack>
        </div>
      </Card>
    </BlockStack>
  );
}

const INSIGHT_STYLES: Record<
  string,
  { bg: string; border: string; emoji: string }
> = {
  success: { bg: "#F0FDF4", border: "#BBF7D0", emoji: "✅" },
  info: { bg: "#EFF6FF", border: "#BFDBFE", emoji: "💡" },
  warning: { bg: "#FEF3C7", border: "#FCD34D", emoji: "⚠️" },
  critical: { bg: "#FEF2F2", border: "#FECACA", emoji: "🚨" },
};

function TrendsCard({
  trends,
  symbol,
}: {
  trends: { date: string; impressions: number; revenue: number }[];
  symbol: string;
}) {
  const total = trends.reduce((sum, t) => sum + t.revenue, 0);
  const max = Math.max(...trends.map((t) => t.revenue), 1);

  return (
    <Card>
      <div style={{ padding: "24px" }}>
        <BlockStack gap="300">
          <InlineStack align="space-between" blockAlign="center">
            <BlockStack gap="100">
              <Text variant="headingMd" as="h3">
                📈 Revenue over time
              </Text>
              <Text as="p" tone="subdued">
                Accepted offer revenue per day in the selected window
              </Text>
            </BlockStack>
            <Badge tone="info" size="large">
              {`${symbol}${total.toLocaleString()} total`}
            </Badge>
          </InlineStack>

          {trends.length === 0 ? (
            <div
              style={{
                padding: "24px",
                backgroundColor: "#FAFAFA",
                borderRadius: "12px",
                border: "1px solid #E5E7EB",
                textAlign: "center",
              }}
            >
              <Text as="p" variant="bodyMd" tone="subdued">
                No revenue in this window yet — accepted offers will show up
                here day by day.
              </Text>
            </div>
          ) : (
            <>
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-end",
                  gap: "3px",
                  height: "140px",
                  padding: "8px",
                  backgroundColor: "#FAFAFA",
                  borderRadius: "12px",
                  border: "1px solid #E5E7EB",
                }}
              >
                {trends.map((t) => {
                  const height = Math.max(
                    3,
                    Math.round((t.revenue / max) * 100),
                  );
                  return (
                    <div
                      key={t.date}
                      title={`${t.date}: ${symbol}${t.revenue.toLocaleString()} (${t.impressions} shown)`}
                      style={{
                        flex: 1,
                        height: `${height}%`,
                        minWidth: "4px",
                        background:
                          "linear-gradient(180deg, #34D399 0%, #059669 100%)",
                        borderRadius: "3px 3px 0 0",
                      }}
                    />
                  );
                })}
              </div>
              <InlineStack align="space-between">
                <Text as="p" variant="bodySm" tone="subdued">
                  {trends[0].date}
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  {trends[trends.length - 1].date}
                </Text>
              </InlineStack>
            </>
          )}
        </BlockStack>
      </div>
    </Card>
  );
}

function FunnelTab({ data }: { data: ImpactDashboardData }) {
  if (data.funnels.length === 0) {
    return (
      <Card>
        <div style={{ padding: "24px", textAlign: "center" }}>
          <Text as="p" variant="bodyMd" tone="subdued">
            No funnel data yet. Offers need to be shown before the funnel
            appears.
          </Text>
        </div>
      </Card>
    );
  }

  return (
    <BlockStack gap="400">
      {data.funnels.map((row) => {
        const isApollo = row.surface === "apollo";
        return (
          <Card key={row.surface}>
            <div style={{ padding: "20px" }}>
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="center">
                  <Text variant="headingMd" as="h3">
                    {isApollo ? "⚡ Apollo (Post-Purchase)" : "🛒 Mercury (Checkout)"}
                  </Text>
                  <Badge tone="info">
                    {`${row.conversionRate.toFixed(1)}% conv.`}
                  </Badge>
                </InlineStack>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                    gap: "12px",
                  }}
                >
                  {[
                    { label: "👀 Impressions", value: row.impressions.toLocaleString() },
                    { label: "✅ Accepted", value: row.accepts.toLocaleString() },
                    { label: "💰 Revenue", value: `$${row.revenue.toLocaleString()}` },
                  ].map((stat) => (
                    <div
                      key={stat.label}
                      style={{
                        padding: "16px",
                        backgroundColor: isApollo ? "#F5F3FF" : "#EFF6FF",
                        borderRadius: "12px",
                        border: `1px solid ${isApollo ? "#DDD6FE" : "#BFDBFE"}`,
                      }}
                    >
                      <BlockStack gap="100">
                        <Text as="p" variant="bodySm" tone="subdued">
                          {stat.label}
                        </Text>
                        <Text as="p" variant="headingLg" fontWeight="bold">
                          {stat.value}
                        </Text>
                      </BlockStack>
                    </div>
                  ))}
                </div>
              </BlockStack>
            </div>
          </Card>
        );
      })}
    </BlockStack>
  );
}

function OffersTab({ data }: { data: ImpactDashboardData }) {
  if (data.topOffers.length === 0) {
    return (
      <Card>
        <div style={{ padding: "24px", textAlign: "center" }}>
          <Text as="p" variant="bodyMd" tone="subdued">
            No offer data yet. Accepted offers will appear here.
          </Text>
        </div>
      </Card>
    );
  }

  const renderOfferRow = (
    offer: (typeof data.topOffers)[number],
  ) => (
    <div
      key={offer.productIdA + offer.productIdB + offer.conversionRate}
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
      <Text as="p" variant="bodyMd">{offer.impressions} shown</Text>
      <Text as="p" variant="bodyMd">{offer.accepts} accepted</Text>
      <Text as="p" variant="bodyMd">${offer.revenue.toLocaleString()}</Text>
      <Text as="p" variant="bodyMd">{offer.conversionRate.toFixed(1)}%</Text>
    </div>
  );

  return (
    <BlockStack gap="400">
      {/* Top Performing Offers */}
      <Card>
        <div style={{ padding: "20px" }}>
          <BlockStack gap="200">
            <div
              style={{
                padding: "16px",
                backgroundColor: "#F0FDF4",
                borderRadius: "12px",
                border: "1px solid #BBF7D0",
              }}
            >
              <Text as="h3" variant="headingMd" fontWeight="bold">
                🏆 Top Performing Offers
              </Text>
            </div>
            {data.topOffers.map(renderOfferRow)}
          </BlockStack>
        </div>
      </Card>

      {/* Worst Performing Offers */}
      <Card>
        <div style={{ padding: "20px" }}>
          <BlockStack gap="200">
            <div
              style={{
                padding: "16px",
                backgroundColor: "#FEF2F2",
                borderRadius: "12px",
                border: "1px solid #FECACA",
              }}
            >
              <Text as="h3" variant="headingMd" fontWeight="bold" tone="critical">
                📉 Worst Performing Offers
              </Text>
            </div>
            {data.worstOffers.map(renderOfferRow)}
          </BlockStack>
        </div>
      </Card>
    </BlockStack>
  );
}