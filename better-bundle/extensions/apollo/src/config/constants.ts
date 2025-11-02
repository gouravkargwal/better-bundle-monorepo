/**
 * Centralized constants for Apollo Extension
 */

export const BACKEND_URL =
  "https://nonconscientious-annette-saddeningly.ngrok-free.dev" as const;

export const SHOPIFY_APP_URL = "https://4edae356409a.ngrok-free.app" as const;

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
