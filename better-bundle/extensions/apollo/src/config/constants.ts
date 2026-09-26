/**
 * Centralized constants for Apollo Extension
 *
 * BACKEND_URL and SHOPIFY_APP_URL are injected at build time by Shopify CLI:
 * it replaces `process.env.VITE_BACKEND_URL` and `process.env.VITE_SHOPIFY_APP_URL`
 * with their current values. Set them in your shell before running
 * `shopify app dev` or `shopify app deploy`, e.g.:
 *
 *   VITE_BACKEND_URL=https://api.betterbundle.online shopify app dev
 *
 * Production fallbacks are provided so the extension never ships a broken URL
 * if the env vars are accidentally unset.
 */

// Backend API base URL — the ONE place to change it for this extension.
//
// Extensions run in the shopper's browser, so this must be a publicly
// reachable host: localhost is not visible to them. During local development
// that means a tunnel to the Python worker on port 8000.
export const BACKEND_URL: string =
  process.env.VITE_BACKEND_URL || "https://api.betterbundle.online";

// The Remix app's own URL. Apollo posts the post-purchase changeset here to
// be signed, so a stale value fails the whole post-purchase step with
// ERR_CONNECTION_REFUSED.
export const SHOPIFY_APP_URL: string =
  process.env.VITE_SHOPIFY_APP_URL || "https://betterbundle.online";

// Storage Keys - Apollo uses in-memory cache for tokens (not persistent)
// These are mainly for reference/compatibility
export const STORAGE_KEYS = {
  // JWT Token Storage (in-memory only for Apollo)
  JWT_TOKEN: "bb_jwt_token",
  JWT_REFRESH_TOKEN: "bb_refresh_token",
  JWT_TOKEN_EXPIRY: "bb_jwt_expiry",
  SHOP_DOMAIN: "bb_shop_domain",
  // Session Storage
  SESSION_ID: "bb_session_id",
  SESSION_EXPIRES_AT: "bb_session_expires_at",
  CLIENT_ID: "bb_client_id",
  BROWSER_SESSION_ID: "bb_browser_session_id",
} as const;

export type StorageKey = (typeof STORAGE_KEYS)[keyof typeof STORAGE_KEYS];
