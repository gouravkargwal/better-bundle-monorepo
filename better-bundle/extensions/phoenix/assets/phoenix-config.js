/**
 * Phoenix Recommendations - Configuration
 * Centralized configuration for all Phoenix modules
 */

// Configuration object for maintainability
const PhoenixConfig = {
  // Performance settings
  CART_CACHE_TTL: 5000, // 5 seconds
  RATE_LIMIT_DELAY: 100, // 100ms between requests
  MAX_QUEUE_SIZE: 100, // Maximum queued requests
  MAX_RETRY_ATTEMPTS: 3, // Retry failed requests

  // Attribution settings
  ATTRIBUTION_EXPIRY_DAYS: 30, // Attribution window

  // API settings
  API_TIMEOUT: 10000, // 10 seconds
  RETRY_BACKOFF_BASE: 1000, // 1 second base delay

  // Accessibility settings
  ARIA_LIVE_DELAY: 1000, // 1 second delay for screen readers

  // Initialize namespace
  init: function () {
    if (!window.PhoenixRecommendations) {
      window.PhoenixRecommendations = {
        state: {
          requestQueue: new Map(),
          requestInProgress: new Set(),
          queueProcessor: null,
          cartCache: { data: null, timestamp: 0 },
          analyticsQueue: []
        },
        config: this
      };
    }
  }
};