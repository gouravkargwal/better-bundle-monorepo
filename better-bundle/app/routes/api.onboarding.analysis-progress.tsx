import { type LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

/**
 * GET /api/onboarding/analysis-progress
 *
 * Returns a JSON status object — the client polls this every 3s.
 *
 * Response shape:
 *   { stage: "checking"|"training"|"complete"|"error",
 *     progress: 0..1,
 *     detail?: string,
 *     productsSynced?: number }
 *
 * Backs onto the worker's edge-pipeline status (`/api/v1/edges/status`):
 * the shop is "ready" once it has at least one servable edge, which is the
 * guarantee that recommendations can actually be served.
 */
export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);

  const shopRecord = await prisma.shops.findUnique({
    where: { shop_domain: session.shop },
    select: { id: true },
  });
  if (!shopRecord) {
    return json({ stage: "error", progress: 0, detail: "Shop not found" });
  }
  const shopId = shopRecord.id;

  const backendUrl = process.env.PYTHON_WORKER_API_URL;
  if (!backendUrl) {
    return json({
      stage: "error",
      progress: 0,
      detail: "Analysis backend not configured",
    });
  }

  try {
    const response = await fetch(`${backendUrl}/api/v1/edges/status/${shopId}`, {
      signal: AbortSignal.timeout(5_000),
    });

    if (!response.ok) {
      return json({
        stage: "checking",
        progress: 0,
        detail: "Waiting for analysis pipeline...",
      });
    }

    const data = await response.json();
    const productsSynced = Number(data?.products) || 0;
    const totalEdges = Number(data?.total_edges) || 0;
    const servable = data?.servable === true;

    if (servable && totalEdges > 0) {
      return json({
        stage: "complete" as const,
        progress: 1,
        productsSynced,
      });
    }

    return json({
      stage: "training" as const,
      progress: Math.min(productsSynced > 0 ? 0.5 + totalEdges / 1000 : 0, 0.95),
      productsSynced,
      detail:
        productsSynced > 0
          ? `Analyzed ${productsSynced} products`
          : "Analyzing product catalog...",
    });
  } catch {
    return json({
      stage: "checking",
      progress: 0,
      detail: "Waiting for analysis pipeline...",
    });
  }
}