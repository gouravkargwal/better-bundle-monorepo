import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../../../shopify.server";
import { getDateRangeFromUrl } from "../../../utils/datetime";
import prisma from "../../../db.server";

export async function loadProductsData({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const url = new URL(request.url);
  const { startDate, endDate } = getDateRangeFromUrl(url);

  try {
    // Get shop info
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: session.shop },
      select: { id: true, currency_code: true },
    });

    if (!shop) {
      return json({ error: "Shop not found" }, { status: 404 });
    }

    // Parse dates
    const start = new Date(startDate + "T00:00:00.000Z");
    const end = new Date(endDate + "T23:59:59.999Z");

    // Get products-specific data only
    const topProducts = await getTopProducts(
      shop.id,
      start,
      end,
      10,
      shop.currency_code || "USD",
    );

    return json({
      topProducts,
      startDate,
      endDate,
    });
  } catch (error) {
    console.error("Products data error:", error);
    return json({ error: "Failed to load products data" }, { status: 500 });
  }
}

async function getTopProducts(
  shopId: string,
  startDate: Date,
  endDate: Date,
  limit: number,
  currencyCode: string,
) {
  // Get product interactions
  const interactions = await prisma.user_interactions.findMany({
    where: {
      shop_id: shopId,
      created_at: { gte: startDate, lte: endDate },
      interaction_type: {
        in: [
          "recommendation_viewed",
          "product_viewed",
          "recommendation_add_to_cart",
          "product_added_to_cart",
        ],
      },
    },
    select: {
      interaction_type: true,
      interaction_metadata: true,
      customer_id: true,
    },
  });

  // Aggregate product stats
  const productStats = new Map<
    string,
    { views: number; clicks: number; customers: Set<string> }
  >();

  interactions.forEach((interaction) => {
    let productId: string | null = null;
    const metadata = interaction.interaction_metadata as any;

    // Extract product ID from different metadata structures
    if (metadata?.data?.recommendations) {
      productId = metadata.data.recommendations[0]?.id;
    } else if (metadata?.data?.productVariant?.product?.id) {
      productId = metadata.data.productVariant.product.id;
    } else if (metadata?.data?.cartLine?.merchandise?.product?.id) {
      productId = metadata.data.cartLine.merchandise.product.id;
    }

    if (!productId) return;

    if (!productStats.has(productId)) {
      productStats.set(productId, {
        views: 0,
        clicks: 0,
        customers: new Set(),
      });
    }

    const stats = productStats.get(productId)!;

    if (
      interaction.interaction_type === "recommendation_viewed" ||
      interaction.interaction_type === "product_viewed"
    ) {
      stats.views++;
    } else if (
      interaction.interaction_type === "recommendation_add_to_cart" ||
      interaction.interaction_type === "product_added_to_cart"
    ) {
      stats.clicks++;
    }

    if (interaction.customer_id) {
      stats.customers.add(interaction.customer_id);
    }
  });

  // Get product titles
  const productIds = Array.from(productStats.keys());
  const products = await prisma.product_data.findMany({
    where: { product_id: { in: productIds }, shop_id: shopId },
    select: { product_id: true, title: true },
  });

  const titleMap = new Map(products.map((p) => [p.product_id, p.title]));

  // Format results
  return Array.from(productStats.entries())
    .map(([productId, stats]) => ({
      product_id: productId,
      title: titleMap.get(productId) || `Product ${productId}`,
      revenue: 0, // No reliable per-product attribution yet
      clicks: stats.clicks,
      conversion_rate:
        stats.views > 0
          ? Math.round((stats.clicks / stats.views) * 100 * 100) / 100
          : 0,
      recommendations_shown: stats.views,
      currency_code: currencyCode,
      customers: stats.customers.size,
    }))
    .sort((a, b) =>
      a.conversion_rate !== b.conversion_rate
        ? b.conversion_rate - a.conversion_rate
        : b.clicks - a.clicks,
    )
    .slice(0, limit);
}
