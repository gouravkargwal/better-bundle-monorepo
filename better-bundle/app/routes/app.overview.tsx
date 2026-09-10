// app/routes/app.overview.tsx
//
// Home — the page the merchant lands on. Two states:
//  - Edges servable → the Home page (cycle money, placements, top products).
//  - Still analysing → the "Setting up…" modal, which polls the worker and
//    hands off once the pipeline is ready.
//
// The path stays /app/overview: in an embedded app the merchant never sees a
// URL, so renaming the route would cost a redirect stub and rewriting every
// internal link while buying nothing. The nav label and the component are what
// the merchant and the next developer read, and both now say Home.
import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData, useRevalidator } from "@remix-run/react";
import { routeErrorBoundary } from "../components/UI/RouteError";
import { useCallback } from "react";
import { authenticate } from "../shopify.server";
import { Card, Page, Text, BlockStack } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { getHomeData } from "../features/overview/services/home.service";
import { HomePage } from "../features/overview/components/HomePage";
import { AnalysisModal } from "../features/overview/components/AnalysisModal";
import logger from "../utils/logger";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    const data = await getHomeData(session.shop);
    return json({
      ok: true as const,
      ...data,
    });
  } catch (error) {
    logger.error({ error, shop: session.shop }, "Home loader error");
    return json(
      {
        ok: false as const,
        error:
          error instanceof Error
            ? error.message
            : "Failed to load your dashboard",
      },
      { status: 500 },
    );
  }
};

export default function Home() {
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
        <TitleBar title="Home" />
        <Card>
          <div style={{ padding: "24px", textAlign: "center" }}>
            <Text as="p" variant="bodyMd" tone="subdued">
              Failed to load your dashboard. Please reload the page.
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
          <TitleBar title="Home" />
          <BlockStack gap="300">
            <Card>
              <BlockStack gap="200" inlineAlign="center">
                <Text as="h2" variant="headingLg" fontWeight="bold" tone="subdued">
                  Analysing your catalogue
                </Text>
                <Text as="p" variant="bodyMd" tone="subdued">
                  We're reading your products and past orders to work out which
                  items sell together. This usually takes a few minutes — you
                  can leave this page and come back.
                </Text>
              </BlockStack>
            </Card>
          </BlockStack>
        </Page>

        <AnalysisModal initiallyReady={false} onComplete={handleComplete} />
      </>
    );
  }

  return <HomePage data={loaderData} />;
}

export const ErrorBoundary = routeErrorBoundary;
