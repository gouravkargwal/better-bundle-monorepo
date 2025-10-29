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

// Unified Analytics API endpoints
export const API_ENDPOINTS = {
  UNIFIED_ANALYTICS_BASE: "/api/atlas",
  TRACK_INTERACTION: "/api/atlas/track-interaction",
  GET_OR_CREATE_SESSION: "/api/atlas/get-or-create-session",
  TRACK_PAGE_VIEW: "/api/atlas/track-page-view",
  TRACK_PRODUCT_VIEW: "/api/atlas/track-product-view",
  TRACK_SEARCH: "/api/atlas/track-search",
  TRACK_FORM_SUBMISSION: "/api/atlas/track-form-submission",
} as const;
export const BACKEND_URL =
  "https://nonconscientious-annette-saddeningly.ngrok-free.dev" as const;
