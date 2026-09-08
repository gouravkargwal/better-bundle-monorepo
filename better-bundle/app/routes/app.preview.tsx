import { json, type LoaderFunctionArgs, type ActionFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { PreviewPage } from "../features/preview/components/PreviewPage";
import type { PreviewProduct } from "../features/preview/types/preview.types";
import logger from "../utils/logger";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, currency_code: true },
    });
    if (!shopRecord) {
      return json({ error: "Shop not found" }, { status: 404 });
    }

    const productRows = await prisma.product_data.findMany({
      where: { shop_id: shopRecord.id, is_active: true },
      select: {
        product_id: true,
        title: true,
        images: true,
      },
      orderBy: { title: "asc" },
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
      shopCurrency: shopRecord.currency_code || "USD",
      products,
    });
  } catch (error) {
    logger.error({ error, shop }, "Preview loader error");
    return json({ error: "Failed to load preview" }, { status: 500 });
  }
};

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
      return json(
        { error: "Analysis backend not configured" },
        { status: 500 },
      );
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
      logger.error(
        { status: response.status, text, shop },
        "Preview fetch failed",
      );
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

export default function PreviewRoute() {
  const data = useLoaderData<typeof loader>();

  if ("error" in data) {
    return (
      <PreviewPage shopCurrency="USD" products={[]} />
    );
  }

  return <PreviewPage shopCurrency={data.shopCurrency} products={data.products} />;
}