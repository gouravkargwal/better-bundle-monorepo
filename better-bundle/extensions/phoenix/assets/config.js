const BASE_URL = 'https://nonconscientious-annette-saddeningly.ngrok-free.dev';

const getBaseUrl = () => {
  return BASE_URL;
};

// Storage Keys - Centralized storage key constants (matching other extensions)
const STORAGE_KEYS = {
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

window.getBaseUrl = getBaseUrl;
window.STORAGE_KEYS = STORAGE_KEYS;
