// features/overview/components/OverviewPage.tsx
import {
  Page,
  Card,
  BlockStack,
  InlineStack,
  Text,
  Badge,
  Banner,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { HeroHeader } from "../../../components/UI/HeroHeader";
import type { OverviewData, SurfaceStatus } from "../types/overview.types";

interface OverviewPageProps {
  data: OverviewData;
}

const SURFACE_LINKS: Record<string, string> = {
  mercury: "checkout settings",
  apollo: "post-purchase settings",
  thank_you: "theme editor",
  phoenix: "theme editor",
  venus: "theme editor",
};

export function OverviewPage({ data }: OverviewPageProps) {
  const { impact, edges, surfaces, topProducts, shopCurrency } = data;
  const { summary, holdoutConfig } = impact;
  const symbol = shopCurrency === "USD" ? "$" : "";

  const liveCount = surfaces.filter((s) => s.status === "live").length;
  const isSignificant = summary.isSignificant;

  return (
    <Page>
      <TitleBar title="Overview" />
      <BlockStack gap="300">
        <HeroHeader
          title="Recommendations that grow with your store"
          subtitle="See what's live, what they're driving, and which products your shoppers are responding to — all in one place."
          variant="gradient"
          align="left"
        />

        {!edges.reachable && (
          <Banner tone="warning">
            <Text as="p" variant="bodyMd">
              <strong>Can't reach the analysis engine.</strong>{" "}
              Recommendations may not be serving right now. Check that the
              worker is running, then reload this page.
            </Text>
          </Banner>
        )}

        {/* Headline metrics */}
        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <Text variant="headingMd" as="h3">
                    💰 Revenue Impact
                  </Text>
                  <Text as="p" tone="subdued">
                    Measured against a control group — not attributed numbers
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
                <BlockStack gap="100">
                  <Text as="h3" variant="heading2xl" fontWeight="bold">
                    {symbol}
                    {summary.incrementalRevenue.toLocaleString()}
                  </Text>
                  <Text as="p" variant="bodyMd" fontWeight="medium">
                    +{summary.aovLiftPercent.toFixed(1)}% AOV lift vs. control ·
                    {summary.totalAccepts.toLocaleString()} offers accepted
                  </Text>
                </BlockStack>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                  gap: "12px",
                }}
              >
                <StatTile
                  label="✅ Offers accepted"
                  value={summary.totalAccepts.toLocaleString()}
                />
                <StatTile
                  label="👀 Offers shown"
                  value={summary.treatmentOrders.toLocaleString()}
                />
                <StatTile
                  label="🎛️ Control sessions"
                  value={summary.controlOrders.toLocaleString()}
                />
                <StatTile
                  label="🧪 Holdout"
                  value={holdoutConfig.enabled ? `${holdoutConfig.percent}%` : "Off"}
                />
              </div>
            </BlockStack>
          </div>
        </Card>

        {/* Surface status */}
        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <Text variant="headingMd" as="h3">
                    🎛️ Where recommendations are live
                  </Text>
                  <Text as="p" tone="subdued">
                    "No traffic yet" usually means the block isn't placed in
                    Shopify yet — see the Extensions page.
                  </Text>
                </BlockStack>
                <Badge tone="info" size="large">
                  {`${liveCount} of 5 live`}
                </Badge>
              </InlineStack>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                  gap: "12px",
                }}
              >
                {surfaces.map((surface) => (
                  <SurfaceCard
                    key={surface.key}
                    surface={surface}
                    currencySymbol={symbol}
                  />
                ))}
              </div>
            </BlockStack>
          </div>
        </Card>

        {/* Top products */}
        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="300">
              <Text variant="headingMd" as="h3">
                🏆 Top recommended products
              </Text>

              {topProducts.length === 0 ? (
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
                    No accepted offers yet. Once shoppers accept recommendations,
                    your top products will appear here.
                  </Text>
                </div>
              ) : (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                    gap: "12px",
                  }}
                >
                  {topProducts.map((product, index) => (
                    <div
                      key={product.productId}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        padding: "12px",
                        backgroundColor: index === 0 ? "#F0FDF4" : "#FAFAFA",
                        borderRadius: "12px",
                        border: `1px solid ${
                          index === 0 ? "#BBF7D0" : "#E5E7EB"
                        }`,
                      }}
                    >
                      {product.imageUrl ? (
                        <img
                          src={product.imageUrl}
                          alt=""
                          width="44"
                          height="44"
                          style={{
                            borderRadius: "8px",
                            objectFit: "cover",
                            flexShrink: 0,
                          }}
                        />
                      ) : (
                        <div
                          style={{
                            width: 44,
                            height: 44,
                            borderRadius: 8,
                            background: "#E5E7EB",
                            flexShrink: 0,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: 16,
                            color: "#6B7280",
                          }}
                        >
                          {product.title.charAt(0).toUpperCase()}
                        </div>
                      )}
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <Text
                          as="p"
                          variant="bodyMd"
                          fontWeight="semibold"
                          truncate
                        >
                          {index === 0 ? "🥇 " : ""}
                          {product.title}
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          {product.accepts} accepted · {symbol}
                          {product.revenue.toLocaleString()} revenue
                        </Text>
                      </div>
                      {product.price !== null && (
                        <Text
                          as="p"
                          variant="bodySm"
                          tone="subdued"
                          fontWeight="medium"
                        >
                          {symbol}
                          {product.price.toFixed(2)}
                        </Text>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </BlockStack>
          </div>
        </Card>

        {edges.products > 0 && (
          <Text as="p" variant="bodySm" tone="subdued">
            {edges.products.toLocaleString()} products analyzed ·{" "}
            {edges.totalEdges.toLocaleString()} recommendation edges ·{" "}
            {edges.observedEdges.toLocaleString()} from real orders
          </Text>
        )}
      </BlockStack>
    </Page>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        padding: "16px",
        backgroundColor: "#EFF6FF",
        borderRadius: "12px",
        border: "1px solid #BFDBFE",
      }}
    >
      <BlockStack gap="050">
        <Text as="p" variant="bodySm" tone="subdued">
          {label}
        </Text>
        <Text as="p" variant="headingLg" fontWeight="bold">
          {value}
        </Text>
      </BlockStack>
    </div>
  );
}

function SurfaceCard({
  surface,
  currencySymbol,
}: {
  surface: SurfaceStatus;
  currencySymbol: string;
}) {
  const config =
    surface.status === "live"
      ? {
          bg: "#F0FDF4",
          border: "#BBF7D0",
          badge: (
            <Badge tone="success" size="small">
              Live
            </Badge>
          ),
        }
      : surface.status === "no_traffic"
        ? {
            bg: "#FEF3C7",
            border: "#FCD34D",
            badge: (
              <Badge tone="attention" size="small">
                No traffic yet
              </Badge>
            ),
          }
        : {
            bg: "#FAFAFA",
            border: "#E5E7EB",
            badge: (
              <Badge tone="critical" size="small">
                Turned off
              </Badge>
            ),
          };

  return (
    <div
      style={{
        padding: "16px",
        backgroundColor: config.bg,
        borderRadius: "12px",
        border: `1px solid ${config.border}`,
      }}
    >
      <BlockStack gap="200">
        <InlineStack align="space-between" blockAlign="center">
          <InlineStack gap="200" blockAlign="center">
            <span style={{ fontSize: "20px" }}>{surface.emoji}</span>
            <Text as="p" variant="bodyMd" fontWeight="semibold">
              {surface.label}
            </Text>
          </InlineStack>
          {config.badge}
        </InlineStack>

        {surface.status === "live" ? (
          <Text as="p" variant="bodySm" tone="subdued">
            {surface.impressions.toLocaleString()} shown ·{" "}
            {surface.accepts.toLocaleString()} accepted · {currencySymbol}
            {surface.revenue.toLocaleString()} revenue
          </Text>
        ) : surface.status === "no_traffic" ? (
          <Text as="p" variant="bodySm" tone="subdued">
            {surface.enabled
              ? `Enabled but nothing served yet — make sure the ${
                  SURFACE_LINKS[surface.key] ?? "block"
                } is set up.`
              : "Turned off in Settings."}
          </Text>
        ) : (
          <Text as="p" variant="bodySm" tone="subdued">
            Disabled in Settings — recommendations won't show here.
          </Text>
        )}
      </BlockStack>
    </div>
  );
}