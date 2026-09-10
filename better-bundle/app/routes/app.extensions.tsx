import {
  json,
  type ActionFunctionArgs,
  type LoaderFunctionArgs,
} from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { BlockStack, Card, Divider, Page } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";

import { ExtensionSetupGuide } from "../components/Extensions/ExtensionSetupGuide";
import { routeErrorBoundary } from "../components/UI/RouteError";
import { PreviewPanel } from "../features/preview/components/PreviewPanel";
import type { PreviewProduct } from "../features/preview/types/preview.types";
import prisma from "../db.server";
import { authenticate } from "../shopify.server";
import logger from "../utils/logger";

/**
 * Setup: install each placement, then check what shoppers will see.
 *
 * Absorbs what used to be a separate `/app/preview` route. Previewing is the
 * "did my install actually work" step — the same job as installing, five
 * minutes later — and it was costing a permanent navigation slot to serve a
 * task a merchant does once. As a section here it sits exactly where someone
 * who has just added a block is already looking.
 */

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  // Idempotent; drives the "finish setup" nudge elsewhere in the app.
  await prisma.shops.update({
    where: { shop_domain: session.shop },
    data: { setup_guide_visited: true },
  });

  const shopRecord = await prisma.shops.findUnique({
    where: { shop_domain: session.shop },
    select: { id: true, currency_code: true },
  });
  if (!shopRecord) {
    throw new Response("Shop not found", { status: 404 });
  }

  const productRows = await prisma.product_data.findMany({
    where: { shop_id: shopRecord.id, is_active: true },
    select: { product_id: true, title: true, images: true },
    orderBy: { title: "asc" },
    // ponytail: unpaginated. Fine at a few thousand SKUs; add server-side
    // search when a merchant with a large catalogue complains.
    take: 1000,
  });

  const products: PreviewProduct[] = productRows.map((row) => {
    const images = (row.images as Array<Record<string, unknown>> | null) ?? [];
    const firstImage = images[0] as { url?: string } | undefined;
    return {
      productId: row.product_id,
      title: row.title,
      imageUrl: firstImage?.url ?? null,
    };
  });

  return json({
    shopDomain: session.shop,
    shopCurrency: shopRecord.currency_code || "USD",
    products,
  });
};

/** Dry-run recommendation fetch for the preview panel. Records nothing. */
export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    const body = await request.json();
    const productIds = Array.isArray(body.productIds)
      ? body.productIds.map(String).filter(Boolean)
      : [];
    const surface = typeof body.surface === "string" ? body.surface : "mercury";

    if (productIds.length === 0) {
      return json({ error: "Select at least one product" }, { status: 400 });
    }

    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true },
    });
    if (!shopRecord) {
      return json({ error: "Shop not found" }, { status: 404 });
    }

    const backendUrl = process.env.PYTHON_WORKER_API_URL;
    if (!backendUrl) {
      return json({ error: "Analysis backend not configured" }, { status: 500 });
    }

    const query = new URLSearchParams({
      product_ids: productIds.join(","),
      surface,
      limit: "6",
    });

    const response = await fetch(
      `${backendUrl}/api/v1/edges/preview/${shopRecord.id}?${query}`,
      { signal: AbortSignal.timeout(10_000) },
    );

    if (!response.ok) {
      const text = await response.text();
      logger.error({ status: response.status, text, shop }, "Preview fetch failed");
      return json(
        { error: `Analysis backend returned ${response.status}` },
        { status: 502 },
      );
    }

    const data = await response.json();
    return json({
      count: data.count ?? 0,
      items: data.items ?? [],
      surface,
    });
  } catch (error) {
    logger.error({ error, shop }, "Preview action error");
    return json(
      { error: "Failed to fetch preview. Is the analysis backend running?" },
      { status: 500 },
    );
  }
};

export default function Setup() {
  const { shopDomain, shopCurrency, products } = useLoaderData<typeof loader>();

  return (
    <Page
      title="Setup"
      subtitle="Add each placement to your store, then preview what a shopper will see."
    >
      <TitleBar title="Setup" />
      <BlockStack gap="400">

        <ExtensionSetupGuide shopDomain={shopDomain} />

        <Divider />

        {/* Anchor target for "not installed" links from Home. */}
        <div id="preview">
          <Card>
            <PreviewPanel shopCurrency={shopCurrency} products={products} />
          </Card>
        </div>
      </BlockStack>
    </Page>
  );
}

export const ErrorBoundary = routeErrorBoundary;
