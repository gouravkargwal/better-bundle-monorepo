// Backend API base URL — the ONE place to change it for this extension.
//
// Extensions run in the shopper's browser, so this must be a publicly
// reachable host: localhost is not visible to them. During local development
// that means a tunnel to the Python worker on port 8000.
//
// Production: https://api.betterbundle.site
export const BACKEND_URL = "https://nonconscientious-annette-saddeningly.ngrok-free.dev";

// Storage Keys - Centralized storage key constants
export const STORAGE_KEYS = {
  // JWT Token Storage (sessionStorage)
  JWT_TOKEN: "bb_jwt_token",
  JWT_REFRESH_TOKEN: "bb_refresh_token",
  JWT_TOKEN_EXPIRY: "bb_jwt_expiry",
  SHOP_DOMAIN: "bb_shop_domain",

  // Session Storage (sessionStorage)
  SESSION_ID: "bb_session_id",
  SESSION_EXPIRES_AT: "bb_session_expires_at",
  CLIENT_ID: "bb_client_id",

  // Browser Session Storage (localStorage - persistent across sessions)
  BROWSER_SESSION_ID: "bb_browser_session_id",

  // Recommendation Attribution Storage (sessionStorage)
  RECOMMENDATION_ATTRIBUTION: "recommendation_attribution",
};

