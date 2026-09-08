// app/routes/app.overview.tsx
//
// Merchant landing dashboard. Two states:
//  - Edges servable → the real Overview page (KPIs, surface status, top products).
//  - Still analyzing → the "Analyzing your catalog…" modal, which polls the
//    worker and hands off to the dashboard when the pipeline is ready.
import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData, useRevalidator } from "@remix-run/react";
import { useCallback } from "react";
import { authenticate } from "../shopify.server";
import { Card, Page, Text, BlockStack } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { getOverviewData } from "../features/overview/services/overview.service";
import { OverviewPage } from "../features/overview/components/OverviewPage";
import { AnalysisModal } from "../features/overview/components/AnalysisModal";
import logger from "../utils/logger";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    const data = await getOverviewData(session.shop);
    return json({
      ok: true as const,
      ...data,
    });
  } catch (error) {
    logger.error({ error, shop: session.shop }, "Overview loader error");
    return json(
      {
        ok: false as const,
        error:
          error instanceof Error
            ? error.message
            : "Failed to load overview data",
      },
      { status: 500 },
    );
  }
};

export default function OverviewRoute() {
  const loaderData = useLoaderData<typeof loader>();
  const { revalidate } = useRevalidator();

  const handleComplete = useCallback(() => {
    // Analysis finished (or was skipped) — re-run the loader so the
    // dashboard renders with live data.
    revalidate();
  }, [revalidate]);

  if (!loaderData.ok) {
    return (
      <Page>
        <TitleBar title="Overview" />
        <Card>
          <div style={{ padding: "24px", textAlign: "center" }}>
            <Text as="p" variant="bodyMd" tone="subdued">
              Failed to load overview data. Please reload the page.
            </Text>
          </div>
        </Card>
      </Page>
    );
  }

  const { edges } = loaderData;
  const ready = edges.reachable && edges.servable;

  if (!ready) {
    return (
      <>
        <Page>
          <TitleBar title="Overview" />
          <BlockStack gap="300">
            <Card>
              <BlockStack gap="200" inlineAlign="center">
                <Text as="h2" variant="headingLg" fontWeight="bold" tone="subdued">
                  Setting up your AI recommendations
                </Text>
                <Text as="p" variant="bodyMd" tone="subdued">
                  We're analyzing your catalog, order history, and customers to
                  build personalized recommendations. This usually takes a few
                  minutes.
                </Text>
              </BlockStack>
            </Card>
          </BlockStack>
        </Page>

        <AnalysisModal initiallyReady={false} onComplete={handleComplete} />
      </>
    );
  }

  return <OverviewPage data={loaderData} />;
}