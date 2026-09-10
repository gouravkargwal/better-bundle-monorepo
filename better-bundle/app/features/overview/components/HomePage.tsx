// features/overview/components/HomePage.tsx
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  Divider,
  EmptyState,
  IndexTable,
  InlineGrid,
  InlineStack,
  Page,
  Text,
  Thumbnail,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";

import { MetricTile } from "../../../components/UI/MetricTile";
import { Milestone } from "../../../components/UI/Milestone";
import { ResultState } from "../../../components/UI/ResultState";
import {
  NOT_SERVING_YET,
  NO_ACCEPTED_YET,
} from "../../../components/UI/illustrations";
import { SURFACES, type SurfaceKey } from "../../../lib/surfaces";
import { formatCurrency } from "../../../utils/currency";
import type { HomeData, SurfaceStatus } from "../types/home.types";

/**
 * Home: what recommendations earned, what it costs, and where they're running.
 *
 * Money comes from `commission_records` / `billing_cycles` — the tables the
 * charge is actually computed from — so the figure here and the figure on the
 * invoice cannot diverge. Incrementality is a separate, statistical question,
 * answered by `ResultState`, which shows a currency amount only when the
 * holdout data supports one.
 *
 * All hand-rolled markup is gone: the surface and product card walls are now
 * `IndexTable`, status pills are `Badge`, and the emoji headings and hardcoded
 * hex tiles have been dropped along with the local `SURFACE_LINKS` map — labels
 * and setup links come from `lib/surfaces.ts`, the single registry.
 */

interface HomePageProps {
  data: HomeData;
}

type StatusTone = "success" | "attention" | "info" | undefined;

function surfaceBadge(surface: SurfaceStatus): {
  tone: StatusTone;
  label: string;
} {
  if (surface.status === "disabled")
    return { tone: undefined, label: "Turned off" };
  if (surface.status === "live") return { tone: "success", label: "Live" };
  return { tone: "attention", label: "Not installed" };
}

export function HomePage({ data }: HomePageProps) {
  const {
    cycle,
    proof,
    holdoutPercent,
    edges,
    surfaces,
    topProducts,
    shopCurrency,
  } = data;

  const liveCount = surfaces.filter((s) => s.status === "live").length;

  // Exact counts out of offer_impressions, across all five surfaces.
  const totalImpressions = surfaces.reduce((n, s) => n + s.impressions, 0);
  const nothingServedYet = totalImpressions === 0;

  const surfaceRows = surfaces.map((surface, index) => {
    const meta = SURFACES[surface.key as SurfaceKey];
    const badge = surfaceBadge(surface);
    const rate =
      surface.impressions > 0
        ? `${((surface.accepts / surface.impressions) * 100).toFixed(1)}%`
        : "—";

    return (
      <IndexTable.Row id={surface.key} key={surface.key} position={index}>
        <IndexTable.Cell>
          <InlineStack gap="200" blockAlign="center">
            <Text as="span" fontWeight="semibold">
              {meta?.label ?? surface.label}
            </Text>
            {meta?.plusOnly && <Badge>Plus</Badge>}
          </InlineStack>
        </IndexTable.Cell>
        <IndexTable.Cell>
          <InlineStack gap="200" blockAlign="center">
            <Badge tone={badge.tone}>{badge.label}</Badge>
            {surface.status === "no_traffic" && meta && (
              <Button url={meta.setupHref} variant="plain">
                Set up
              </Button>
            )}
          </InlineStack>
        </IndexTable.Cell>
        {/* An em dash, never a zero — "0" reads as "it tried and failed". */}
        <IndexTable.Cell>
          <Text as="span" numeric>
            {surface.impressions > 0
              ? surface.impressions.toLocaleString()
              : "—"}
          </Text>
        </IndexTable.Cell>
        <IndexTable.Cell>
          <Text as="span" numeric>
            {surface.accepts > 0 ? surface.accepts.toLocaleString() : "—"}
          </Text>
        </IndexTable.Cell>
        <IndexTable.Cell>
          <Text as="span" numeric tone="subdued">
            {rate}
          </Text>
        </IndexTable.Cell>
        <IndexTable.Cell>
          <Text as="span" numeric>
            {surface.revenue > 0
              ? formatCurrency(surface.revenue, shopCurrency)
              : "—"}
          </Text>
        </IndexTable.Cell>
      </IndexTable.Row>
    );
  });

  const productRows = topProducts.map((product, index) => (
    <IndexTable.Row
      id={product.productId}
      key={product.productId}
      position={index}
    >
      <IndexTable.Cell>
        <InlineStack gap="300" blockAlign="center">
          <Thumbnail
            source={product.imageUrl ?? ""}
            alt={product.title}
            size="small"
          />
          <Text as="span" fontWeight="semibold">
            {product.title}
          </Text>
        </InlineStack>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" numeric>
          {product.accepts.toLocaleString()}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" numeric>
          {formatCurrency(product.revenue, shopCurrency)}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" numeric tone="subdued">
          {product.price !== null
            ? formatCurrency(product.price, shopCurrency)
            : "—"}
        </Text>
      </IndexTable.Cell>
    </IndexTable.Row>
  ));

  return (
    <Page
      title="Home"
      subtitle="What your recommendations earned, and what it costs."
    >
      <TitleBar title="Home" />
      <BlockStack gap="400">
        {!edges.reachable && (
          <Banner tone="warning">
            <Text as="p" variant="bodyMd">
              <strong>Can't reach the recommendation engine.</strong> Shoppers
              may not be seeing recommendations right now. The figures below are
              still accurate — they're already recorded.
            </Text>
          </Banner>
        )}

        {/* 0. A moment worth marking, if there is one. Renders nothing most
               of the time — that is the point of a milestone. */}
        {cycle.hasSubscription && (
          <Milestone
            attributedRevenue={cycle.attributedRevenue}
            trialRevenueEarned={cycle.trialRevenueEarned}
            trialThreshold={cycle.trialThreshold}
            isTrial={cycle.isTrial}
            ordersInfluenced={cycle.ordersInfluenced}
            proof={proof}
            currency={cycle.currency}
          />
        )}

        {/* 1. This cycle. The merchant's first question: am I making money and
               what will it cost me? */}
        {cycle.hasSubscription && (
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <Text variant="headingMd" as="h2">
                    {cycle.isTrial ? "Your free trial" : "This billing cycle"}
                  </Text>
                  <Text as="p" tone="subdued">
                    {cycle.isTrial
                      ? `Free until recommendations have earned you ${formatCurrency(cycle.trialThreshold, cycle.currency)}.`
                      : `${(cycle.commissionRate * 100).toFixed(0)}% of attributed revenue, capped at ${formatCurrency(cycle.capAmount, cycle.currency)}.`}
                  </Text>
                </BlockStack>
                <Button url="/app/billing" variant="plain">
                  See charges
                </Button>
              </InlineStack>

              <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="400">
                <MetricTile
                  label="Attributed revenue"
                  value={
                    cycle.attributedRevenue > 0
                      ? formatCurrency(cycle.attributedRevenue, cycle.currency)
                      : "—"
                  }
                  tooltip="Revenue from orders where the shopper interacted with a recommendation. This is the number your commission is calculated on."
                />

                {cycle.isTrial ? (
                  <MetricTile
                    label="Free allowance left"
                    value={formatCurrency(
                      Math.max(
                        0,
                        cycle.trialThreshold - cycle.trialRevenueEarned,
                      ),
                      cycle.currency,
                    )}
                    sub={`${formatCurrency(cycle.trialRevenueEarned, cycle.currency)} of ${formatCurrency(cycle.trialThreshold, cycle.currency)} earned`}
                    progress={{
                      value: cycle.trialRevenueEarned,
                      max: cycle.trialThreshold,
                    }}
                    tooltip="You pay nothing until recommendations have earned you this much. The trial ends on revenue, not on a date."
                  />
                ) : (
                  <MetricTile
                    label="Your bill so far"
                    value={formatCurrency(cycle.billedSoFar, cycle.currency)}
                    sub={`Capped at ${formatCurrency(cycle.capAmount, cycle.currency)}`}
                    progress={{
                      value: cycle.billedSoFar,
                      max: cycle.capAmount,
                    }}
                    tooltip="Commission charged this cycle. You are never charged more than the cap, however much revenue is attributed."
                  />
                )}

                <MetricTile
                  label="Orders influenced"
                  value={
                    cycle.ordersInfluenced > 0
                      ? cycle.ordersInfluenced.toLocaleString()
                      : "—"
                  }
                  tooltip="Orders with at least one recommendation interaction."
                />

                <MetricTile
                  label={cycle.isTrial ? "Commission rate" : "Cycle ends"}
                  value={
                    cycle.isTrial
                      ? `${(cycle.commissionRate * 100).toFixed(0)}%`
                      : cycle.daysLeftInCycle !== null
                        ? `${cycle.daysLeftInCycle} days`
                        : "—"
                  }
                  sub={
                    cycle.isTrial
                      ? "Applies once the trial ends"
                      : cycle.cycleEnd
                        ? new Date(cycle.cycleEnd).toLocaleDateString()
                        : undefined
                  }
                />
              </InlineGrid>

              <Divider />

              {/* 2. Is it working? The only place Home touches incrementality,
                     and it shows no figure unless the result is significant. */}
              <BlockStack gap="200">
                <Text variant="headingSm" as="h3">
                  Is it working?
                </Text>
                <ResultState
                  result={proof}
                  currencyCode={shopCurrency}
                  holdoutPercent={holdoutPercent}
                />
              </BlockStack>
            </BlockStack>
          </Card>
        )}

        {nothingServedYet ? (
          <Card>
            <EmptyState
              heading="No recommendations shown yet"
              action={{ content: "Finish setup", url: "/app/extensions" }}
              secondaryAction={{
                content: "Preview recommendations",
                url: "/app/extensions#preview",
              }}
              image={NOT_SERVING_YET}
            >
              <Text as="p">
                {edges.products > 0
                  ? `${edges.products.toLocaleString()} products are analysed and ready. Recommendations will start appearing once you add a placement to your store.`
                  : "Once your catalogue has been analysed and you've added a placement, your results will appear here."}
              </Text>
            </EmptyState>
          </Card>
        ) : (
          <>
            {/* 3. Where recommendations are running — all five placements,
                   always. The old funnel handled apollo and mercury only, so
                   phoenix, thank_you and venus were invisible. */}
            <Card padding="0">
              <Box padding="400" paddingBlockEnd="200">
                <InlineStack align="space-between" blockAlign="center">
                  <BlockStack gap="100">
                    <Text variant="headingMd" as="h2">
                      Where recommendations are running
                    </Text>
                    <Text as="p" tone="subdued">
                      "Not installed" means the block hasn't been added to your
                      theme or checkout yet.
                    </Text>
                  </BlockStack>
                  <Badge tone="info">{`${liveCount} of ${surfaces.length} live`}</Badge>
                </InlineStack>
              </Box>
              <IndexTable
                resourceName={{ singular: "placement", plural: "placements" }}
                itemCount={surfaceRows.length}
                selectable={false}
                headings={[
                  { title: "Placement" },
                  { title: "Status" },
                  { title: "Shown" },
                  { title: "Accepted" },
                  { title: "Accept rate" },
                  { title: "Attributed revenue" },
                ]}
              >
                {surfaceRows}
              </IndexTable>
            </Card>

            {/* 4. Top recommended products. Deliberately no "worst offers"
                   table — a non-analyst cannot act on it and it reads as an
                   accusation. */}
            <Card padding="0">
              <Box padding="400" paddingBlockEnd="200">
                <Text variant="headingMd" as="h2">
                  Top recommended products
                </Text>
              </Box>
              {topProducts.length === 0 ? (
                <Box padding="400">
                  <EmptyState
                    heading="No accepted recommendations yet"
                    image={NO_ACCEPTED_YET}
                  >
                    <Text as="p">
                      The products shoppers accept most often will appear
                      here.
                    </Text>
                  </EmptyState>
                </Box>
              ) : (
                <IndexTable
                  resourceName={{ singular: "product", plural: "products" }}
                  itemCount={productRows.length}
                  selectable={false}
                  headings={[
                    { title: "Product" },
                    { title: "Accepted" },
                    { title: "Attributed revenue" },
                    { title: "Price" },
                  ]}
                >
                  {productRows}
                </IndexTable>
              )}
            </Card>
          </>
        )}

        {edges.products > 0 && (
          <Text as="p" variant="bodySm" tone="subdued">
            {edges.products.toLocaleString()} products analysed ·{" "}
            {edges.totalEdges.toLocaleString()} recommendation links ·{" "}
            {edges.observedEdges.toLocaleString()} learned from real orders
          </Text>
        )}
      </BlockStack>
    </Page>
  );
}
