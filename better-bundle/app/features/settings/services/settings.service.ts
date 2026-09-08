// features/settings/services/settings.service.ts
//
// The `shops.settings` JSONB column is owned by the python worker (alembic
// migration + SQLAlchemy model). The Remix prisma client only learns about it
// after `prisma db pull`, so we read/write it through raw SQL here. This keeps
// the admin UI working even when the generated client is behind the schema.
import prisma from "../../../db.server";
import type { SurfaceKey } from "../types/settings.types";
import logger from "../../../utils/logger";

const SURFACE_KEYS: SurfaceKey[] = [
  "mercury",
  "apollo",
  "thank_you",
  "phoenix",
  "venus",
];

export interface PersistedShopSettings {
  surfaces?: Partial<Record<SurfaceKey, boolean>>;
  excluded_product_ids?: string[];
}

interface ShopSettingsRow {
  shop_id: string;
  currency_code: string | null;
  holdout_disabled: boolean;
  settings: PersistedShopSettings | null;
}

/**
 * Load a shop's merchant-controlled settings. Missing settings mean "defaults":
 * every surface on, no exclusions.
 */
export async function getShopSettings(shopDomain: string) {
  const rows = await prisma.$queryRaw<ShopSettingsRow[]>`
    SELECT id AS shop_id, currency_code, holdout_disabled, settings
    FROM shops
    WHERE shop_domain = ${shopDomain}
  `;

  const row = rows[0];
  if (!row) {
    return null;
  }

  const raw: PersistedShopSettings =
    (row.settings as PersistedShopSettings | null) ?? {};

  const surfaces: Record<SurfaceKey, boolean> = {
    mercury: true,
    apollo: true,
    thank_you: true,
    phoenix: true,
    venus: true,
  };
  for (const key of SURFACE_KEYS) {
    const value = raw.surfaces?.[key];
    if (typeof value === "boolean") {
      surfaces[key] = value;
    }
  }

  return {
    shopId: row.shop_id,
    shopCurrency: row.currency_code || "USD",
    holdoutDisabled: row.holdout_disabled,
    surfaces,
    excludedProductIds: Array.isArray(raw.excluded_product_ids)
      ? raw.excluded_product_ids.map(String)
      : [],
  };
}

interface SaveSettingsInput {
  surfaces: Record<SurfaceKey, boolean>;
  excludedProductIds: string[];
  holdoutDisabled: boolean;
}

/**
 * Persist settings. `settings` is stored as-is (surface flags + excluded
 * product ids); `holdout_disabled` lives on its own boolean column that the
 * worker already reads.
 */
export async function saveShopSettings(
  shopDomain: string,
  input: SaveSettingsInput,
) {
  const settings: PersistedShopSettings = {
    surfaces: { ...input.surfaces },
    excluded_product_ids: input.excludedProductIds,
  };

  try {
    const result = await prisma.$executeRaw`
      UPDATE shops
      SET settings = ${JSON.stringify(settings)}::jsonb,
          holdout_disabled = ${input.holdoutDisabled},
          updated_at = NOW()
      WHERE shop_domain = ${shopDomain}
    `;
    return result > 0;
  } catch (error) {
    logger.error({ error, shopDomain }, "Failed to save shop settings");
    throw error;
  }
}