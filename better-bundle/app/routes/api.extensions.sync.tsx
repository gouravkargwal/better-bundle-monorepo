import { json, type ActionFunctionArgs, type LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import {
  getShopSettings,
  updateDetectedSurfaces,
} from "../features/settings/services/settings.service";
import logger from "../utils/logger";
import type { SurfaceKey } from "../lib/surfaces";

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const settings = await getShopSettings(session.shop);
  return json({
    success: true,
    detectedSurfaces: settings?.detectedSurfaces ?? {},
  });
}

export async function action({ request }: ActionFunctionArgs) {
  const { session } = await authenticate.admin(request);

  if (request.method !== "POST") {
    return json({ success: false, error: "Method not allowed" }, { status: 405 });
  }

  try {
    const body = await request.json();
    const detectedSurfaces = body?.detectedSurfaces as Partial<Record<SurfaceKey, boolean>> | undefined;

    if (!detectedSurfaces || typeof detectedSurfaces !== "object") {
      return json(
        { success: false, error: "Invalid detectedSurfaces payload" },
        { status: 400 },
      );
    }

    const updated = await updateDetectedSurfaces(session.shop, detectedSurfaces);
    return json({ success: updated });
  } catch (error) {
    logger.error({ error, shop: session.shop }, "Failed to sync detected extensions");
    return json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Sync failed",
      },
      { status: 500 },
    );
  }
}
