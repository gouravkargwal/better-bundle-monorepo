// features/settings/services/surfaceMetafield.server.ts
//
// Mirrors the phoenix on/off flag into an app-data metafield so the theme app
// extension can decide, at Liquid render time, whether to render at all.
//
// Why this exists
// ---------------
// Every other surface is a JS extension: it can fetch first and mount nothing
// if the answer is "disabled", so the shopper never sees anything. Phoenix is a
// Liquid block. Its skeleton ships in the initial HTML, before any JS has run
// and long before our API could say the surface is switched off — so a merchant
// who disables storefront recommendations still gets a skeleton painted and
// then torn down, which reads as a broken widget rather than a disabled one.
//
// Liquid cannot reach Postgres, and an extra blocking request per page render
// is not an option. A metafield is the only channel that carries our state into
// the Liquid render itself.
//
// Ownership: written to the AppInstallation, which makes it an app-data
// metafield — only this app can read it, it never shows in the admin, and it
// needs no extra access scope (the existing token writes it fine).
//
// The namespace is deliberately PLAIN ("config"), not the reserved "$app:config"
// form used for metafields on shop/product owners. On an AppInstallation the
// `$app:` prefix is expanded to `app--<app-id>--config` and stored that way,
// and Liquid's `app.metafields.config` does not match it — the value reads nil
// and the block falls through to its default. A plain namespace is stored
// verbatim, so `app.metafields.config.phoenix_enabled` resolves under either
// behaviour. There is no collision risk: the owner is our own app installation,
// which no other app can address.
//
// This is also the namespace form Shopify's own `available_if` block condition
// documents, which reads the same `{{ app.metafields.namespace.key }}` path.
//
// ponytail: only `phoenix` is mirrored. The other four surfaces are JS and can
// gate themselves on the API response; add them here if one ever needs to be
// known before its own JS runs.
import logger from "../../../utils/logger";

const NAMESPACE = "config";
const KEY = "phoenix_enabled";

interface AdminClient {
  graphql: (
    query: string,
    options?: { variables?: Record<string, unknown> },
  ) => Promise<Response>;
}

const APP_INSTALLATION = `#graphql
  query BetterBundleAppInstallation {
    currentAppInstallation { id }
  }
`;

const METAFIELDS_SET = `#graphql
  mutation BetterBundleSetSurfaceFlag($metafields: [MetafieldsSetInput!]!) {
    metafieldsSet(metafields: $metafields) {
      userErrors { field message code }
    }
  }
`;

/**
 * Publish whether the storefront (phoenix) surface is enabled.
 *
 * Never throws: the shop's own settings row is the source of truth and has
 * already been written by the time this runs. A failure here means the theme
 * block keeps rendering optimistically — exactly the behaviour we had before
 * this existed — and the API still refuses to serve a disabled surface, so no
 * recommendation leaks. Losing the mirror must not fail the merchant's save.
 *
 * Returns whether the mirror landed, so a caller can surface a soft warning.
 */
export async function publishPhoenixEnabled(
  admin: AdminClient,
  shopDomain: string,
  enabled: boolean,
): Promise<boolean> {
  try {
    const installResponse = await admin.graphql(APP_INSTALLATION);
    const installBody = await installResponse.json();
    const ownerId = installBody?.data?.currentAppInstallation?.id;

    if (!ownerId) {
      logger.warn(
        { shopDomain, body: installBody },
        "No currentAppInstallation id; skipped phoenix surface metafield",
      );
      return false;
    }

    const response = await admin.graphql(METAFIELDS_SET, {
      variables: {
        metafields: [
          {
            ownerId,
            namespace: NAMESPACE,
            key: KEY,
            // "boolean" rather than a json blob of all five surfaces: Liquid
            // reads it with no parsing, and a mistyped key in a blob would
            // silently read as nil, which the block would treat as "off".
            type: "boolean",
            value: enabled ? "true" : "false",
          },
        ],
      },
    });

    const body = await response.json();
    const errors = body?.data?.metafieldsSet?.userErrors ?? [];
    if (errors.length > 0) {
      logger.warn(
        { shopDomain, errors },
        "metafieldsSet rejected the phoenix surface flag",
      );
      return false;
    }

    return true;
  } catch (error) {
    logger.warn(
      { error, shopDomain },
      "Could not mirror phoenix surface flag to a metafield",
    );
    return false;
  }
}
