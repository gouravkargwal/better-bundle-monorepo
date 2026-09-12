/**
 * Centralized constants for Apollo Extension
 */

// Backend API base URL — the ONE place to change it for this extension.
//
// Extensions run in the shopper's browser, so this must be a publicly
// reachable host: localhost is not visible to them. During local development
// that means a tunnel to the Python worker on port 8000.
//
// Production: https://api.betterbundle.site
export const BACKEND_URL = "https://nonconscientious-annette-saddeningly.ngrok-free.dev" as const;
// The Remix app's own URL. Apollo posts the post-purchase changeset here to
// be signed, so a stale value fails the whole post-purchase step with
// ERR_CONNECTION_REFUSED — it was pinned to the production domain while
// running against a dev tunnel.
export const SHOPIFY_APP_URL = "https://73e5-223-184-244-44.ngrok-free.app" as const;

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
