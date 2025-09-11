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

// API endpoints
export const API_ENDPOINTS = {
  BEHAVIORAL_EVENTS: "/api/v1/behavioral-events",
  HEALTH_CHECK: "/api/v1/health",
} as const;
