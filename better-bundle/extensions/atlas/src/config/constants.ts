export const PIXEL_VERSION = "1.0.0";
export const PIXEL_NAME = "atlas";

// Standard Shopify events we subscribe to
export const SUBSCRIBABLE_EVENTS = {
  PAGE_VIEWED: "page_viewed",
  PRODUCT_VIEWED: "product_viewed",
  PRODUCT_ADDED_TO_CART: "product_added_to_cart",
  PRODUCT_REMOVED_FROM_CART: "product_removed_from_cart",
  CART_VIEWED: "cart_viewed",
  COLLECTION_VIEWED: "collection_viewed",
  SEARCH_SUBMITTED: "search_submitted",
  CHECKOUT_STARTED: "checkout_started",
  CHECKOUT_COMPLETED: "checkout_completed",
} as const;

// Custom events we publish
export const CUSTOM_EVENTS = {
  CUSTOMER_LINKED: "customer_linked",
} as const;

export type SubscribableEventType =
  (typeof SUBSCRIBABLE_EVENTS)[keyof typeof SUBSCRIBABLE_EVENTS];
export type CustomEventType =
  (typeof CUSTOM_EVENTS)[keyof typeof CUSTOM_EVENTS];

// Default configuration
export const DEFAULT_CONFIG = {
  MAX_RETRIES: 3,
  RETRY_DELAY: 1000,
  DEBUG: false,
} as const;

export const BACKEND_URL =
  "https://nonconscientious-annette-saddeningly.ngrok-free.dev" as const;

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
} as const;

// Type for storage key values
export type StorageKey = (typeof STORAGE_KEYS)[keyof typeof STORAGE_KEYS];
