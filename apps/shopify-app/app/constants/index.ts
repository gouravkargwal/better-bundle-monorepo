// Analysis configuration constants
export const ANALYSIS_CONFIG = {
  DEFAULT_MIN_CONFIDENCE: 0.1,
  DEFAULT_MIN_LIFT: 1.5,
  DEFAULT_MIN_SUPPORT: 0.004,
  DEFAULT_MAX_BUNDLE_SIZE: 4,
  DEFAULT_ANALYSIS_WINDOW: 180,
  MIN_ORDERS_REQUIRED: 5,
  RECOMMENDED_ORDERS: 10,
  MIN_PRODUCTS_REQUIRED: 3,
} as const;

// Progress simulation constants
export const PROGRESS_CONFIG = {
  UPDATE_INTERVAL: 800,
  MIN_INCREMENT: 2,
  MAX_INCREMENT: 8,
  MAX_PROGRESS: 90,
} as const;

// UI constants
export const UI_CONFIG = {
  ITEMS_PER_PAGE: 10,
  PROGRESS_BAR_WIDTH: 300,
} as const;

// Error messages
export const ERROR_MESSAGES = {
  NO_ORDERS: "No orders found in your store",
  INSUFFICIENT_DATA: "Insufficient order data for meaningful analysis",
  NO_PRODUCTS: "Not enough products for bundle analysis",
  VALIDATION_FAILED: "Failed to validate store data",
  ANALYSIS_FAILED: "Failed to start bundle analysis",
  UNKNOWN_ERROR: "An unknown error occurred",
} as const;

// Success messages
export const SUCCESS_MESSAGES = {
  ANALYSIS_COMPLETE: "Analysis completed successfully!",
  VALIDATION_PASSED: "Store validation passed",
} as const;

// Recommendations
export const RECOMMENDATIONS = {
  NO_ORDERS: [
    "Create some test orders in your Shopify admin",
    "Import orders from another platform",
    "Wait for customers to place orders",
  ],
  INSUFFICIENT_DATA: [
    "We recommend at least 10 orders for accurate analysis",
    "Create more test orders with multiple products",
    "Wait for more customer orders",
  ],
  NO_PRODUCTS: [
    "Add more products to your store",
    "Create product variations",
    "Import products from another platform",
  ],
  GENERAL_ERROR: [
    "Please try again",
    "Contact support if the issue persists",
  ],
};
