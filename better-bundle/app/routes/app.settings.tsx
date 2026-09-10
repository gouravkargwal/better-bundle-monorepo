import { json, type LoaderFunctionArgs, type ActionFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { routeErrorBoundary } from "../components/UI/RouteError";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { SettingsPage } from "../features/settings/components/SettingsPage";
import {
  getShopSettings,
  saveShopSettings,
} from "../features/settings/services/settings.service";
import type { SurfaceKey, SettingsProduct } from "../features/settings/types/settings.types";
import logger from "../utils/logger";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    const settings = await getShopSettings(shop);
    if (!settings) {
      return json({ error: "Shop not found" }, { status: 404 });
    }

    // Products for the exclusion picker — synced by the worker into
    // product_data (numeric product ids, matching the edge pipeline).
    const productRows = await prisma.product_data.findMany({
      where: { shop_id: settings.shopId, is_active: true },
      select: {
        product_id: true,
        title: true,
        images: true,
      },
      orderBy: { title: "asc" },
      take: 1000,
    });

    const products: SettingsProduct[] = productRows.map((row) => {
      const images = (row.images as Array<Record<string, unknown>> | null) ?? [];
      const firstImage = images[0] as { url?: string } | undefined;
      return {
        productId: row.product_id,
        title: row.title,
        imageUrl: firstImage?.url ?? null,
      };
    });

    return json({
      shopDomain: shop,
      shopCurrency: settings.shopCurrency,
      surfaces: settings.surfaces,
      holdoutDisabled: settings.holdoutDisabled,
      excludedProductIds: settings.excludedProductIds,
      products,
    });
  } catch (error) {
    logger.error({ error, shop }, "Settings loader error");
    return json({ error: "Failed to load settings" }, { status: 500 });
  }
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    const body = await request.json();

    const surfacesRaw = (body.surfaces ?? {}) as Record<string, unknown>;
    const surfaces: Record<SurfaceKey, boolean> = {
      mercury: true,
      apollo: true,
      thank_you: true,
      phoenix: true,
      venus: true,
    };
    for (const key of Object.keys(surfaces)) {
      const value = surfacesRaw[key];
      if (typeof value === "boolean") {
        surfaces[key as SurfaceKey] = value;
      }
    }

    const excludedProductIds = Array.isArray(body.excludedProductIds)
      ? body.excludedProductIds.map(String)
      : [];
    const holdoutDisabled = body.holdoutDisabled === true;

    const saved = await saveShopSettings(shop, {
      surfaces,
      excludedProductIds,
      holdoutDisabled,
    });

    if (!saved) {
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    return json({ success: true });
  } catch (error) {
    logger.error({ error, shop }, "Settings save error");
    return json(
      { success: false, error: "Failed to save settings" },
      { status: 500 },
    );
  }
};

export default function SettingsRoute() {
  const data = useLoaderData<typeof loader>();

  if ("error" in data) {
    return <SettingsPage
      shopCurrency="USD"
      initialSurfaces={{
        mercury: true,
        apollo: true,
        thank_you: true,
        phoenix: true,
        venus: true,
      }}
      initialHoldoutDisabled={false}
      initialExcludedProductIds={[]}
      products={[]}
      error={data.error}
    />;
  }

  return (
    <SettingsPage
      shopCurrency={data.shopCurrency}
      initialSurfaces={data.surfaces}
      initialHoldoutDisabled={data.holdoutDisabled}
      initialExcludedProductIds={data.excludedProductIds}
      products={data.products}
    />
  );
}

export const ErrorBoundary = routeErrorBoundary;
