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
    const response = await fetch(
      `${backendUrl}/api/v1/gorse/status/${shopId}`,
      { signal: AbortSignal.timeout(5_000) },
    );

    if (!response.ok) {
      return json({
        stage: "checking",
        progress: 0,
        detail: "Waiting for analysis pipeline...",
      });
    }

    const data = await response.json();
    const featureCounts = data?.feature_utilization?.feature_counts || {};
    const productssynced = featureCounts.product_features || 0;
    const qualityScore = data?.quality_indicators?.overall_quality || 0;
    const gorseHealthy = data?.gorse_health?.success === true;

    if (gorseHealthy && productssynced > 0) {
      return json({
        stage: "complete" as const,
        progress: 1,
        productsSynced: productssynced,
        qualityScore,
      });
    }

    return json({
      stage: "training" as const,
      progress: Math.min(qualityScore, 0.95),
      productsSynced: productssynced,
      qualityScore,
      detail:
        productssynced > 0
          ? `Analyzed ${productssynced} products`
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
