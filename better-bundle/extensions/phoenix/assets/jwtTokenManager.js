/**
 * JWT Token Manager for Phoenix Extension
 * Unified pattern matching Atlas, Venus, Mercury, and Apollo extensions
 * Handles JWT token generation, validation, storage, and refresh
 * Includes Phoenix-specific initialization and UI management
 */

class JWTTokenManager {
  constructor() {
    // Use unified storage keys from config
    const STORAGE_KEYS = window.STORAGE_KEYS || {
      JWT_TOKEN: "bb_jwt_token",
      JWT_REFRESH_TOKEN: "bb_refresh_token",
      JWT_TOKEN_EXPIRY: "bb_jwt_expiry",
      SHOP_DOMAIN: "bb_shop_domain",
    };

    this.TOKEN_KEY = STORAGE_KEYS.JWT_TOKEN;
    this.REFRESH_TOKEN_KEY = STORAGE_KEYS.JWT_REFRESH_TOKEN;
    this.TOKEN_EXPIRY_KEY = STORAGE_KEYS.JWT_TOKEN_EXPIRY;
    this.SHOP_DOMAIN_KEY = STORAGE_KEYS.SHOP_DOMAIN;
    // this.BACKEND_URL = window.getBaseUrl ? window.getBaseUrl() : "https://nonconscientious-annette-saddeningly.ngrok-free.dev";
    this.BACKEND_URL = window.getBaseUrl ? window.getBaseUrl() : "https://api.betterbundle.site";

    // Module-level promises for preventing concurrent refresh attempts
    this.refreshPromise = null;
    this.refreshAccessTokenPromise = null;

    // Phoenix-specific state
    this.shopDomain = window.shopDomain || this.getShopDomainFromUrl();
    this.isInitialized = false;
    this.logger = window.phoenixLogger || console;
  }

  /**
   * Initialize Phoenix with JWT authentication
   */
  async initialize() {
    try {
      if (!this.shopDomain) {
        this.disablePhoenixFeatures();
        return;
      }

      // Check sessionStorage first - no API call if token exists and is valid
      const storedToken = this.getStoredToken();
      if (
        storedToken &&
        storedToken.token &&
        storedToken.shopDomain === this.shopDomain &&
        this.isTokenNotExpired(storedToken)
      ) {
        // Token is valid, proceed
      } else {
        // Only make API call if no valid token in sessionStorage
        // Get customerId if available (for customer-specific tokens)
        const customerId = window.customerId || null;
        const token = await this.getValidToken(this.shopDomain, customerId);
        if (!token) {
          // No token available, disable features
          this.disablePhoenixFeatures();
          return;
        }
      }

      this.isInitialized = true;
    } catch (error) {
      // Silently fail and disable features
      this.disablePhoenixFeatures();
    }
  }

  /**
   * Check if Phoenix is initialized
   */
  isReady() {
    return this.isInitialized;
  }

  /**
   * Get shop domain
   */
  getShopDomain() {
    return this.shopDomain;
  }

  /**
   * Get shop domain from URL
   */
  getShopDomainFromUrl() {
    if (typeof window !== "undefined" && window.location) {
      const hostname = window.location.hostname;
      if (hostname.includes(".myshopify.com")) {
        return hostname.replace(".myshopify.com", "");
      }
    }
    return null;
  }

  /**
   * Disable Phoenix features due to suspension or initialization failure
   */
  disablePhoenixFeatures() {
    this.isInitialized = false;

    // Hide Phoenix UI elements
    const phoenixElements = document.querySelectorAll("[data-phoenix]");
    phoenixElements.forEach((element) => {
      element.style.display = "none";
    });

    // Hide recommendation carousels
    const carouselElements = document.querySelectorAll(".shopify-app-block");
    carouselElements.forEach((element) => {
      element.style.display = "none";
    });
  }

  /**
   * Check if token is still valid (not expired)
   */
  isTokenNotExpired(tokenInfo) {
    if (!tokenInfo || !tokenInfo.expiresIn) return false;
    const now = Date.now() / 1000;
    const expiry = tokenInfo.expiresIn;
    return expiry - now > 60; // Valid if expires in more than 60 seconds
  }

  /**
   * Get stored token from sessionStorage
   */
  getStoredToken() {
    try {
      const token = sessionStorage.getItem(this.TOKEN_KEY);
      const shopDomain = sessionStorage.getItem(this.SHOP_DOMAIN_KEY);

      if (!token || !shopDomain) return null;

      return {
        token,
        expiresIn: parseInt(sessionStorage.getItem(this.TOKEN_EXPIRY_KEY) || "0"),
        shopDomain,
        shopStatus: "unknown",
        permissions: [],
      };
    } catch (error) {
      this.logger.error({ error }, "Phoenix pixel: Failed to get stored token");
      return null;
    }
  }

  /**
   * Store token information in sessionStorage
   */
  storeToken(tokenInfo) {
    try {
      sessionStorage.setItem(this.TOKEN_KEY, tokenInfo.token);
      const expiryTimestamp = Math.floor(Date.now() / 1000) + tokenInfo.expiresIn;
      sessionStorage.setItem(this.TOKEN_EXPIRY_KEY, expiryTimestamp.toString());
      sessionStorage.setItem(this.SHOP_DOMAIN_KEY, tokenInfo.shopDomain);
    } catch (error) {
      this.logger.error({ error }, "Phoenix pixel: Failed to store token");
    }
  }

  /**
   * Fetch new token pair (access + refresh) from backend
   */
  async fetchNewTokenPair(shopDomain, customerId = null) {
    const requestBody = { shop_domain: shopDomain };

    if (customerId) {
      requestBody.customer_id = customerId;
    }

    // Use new unified endpoint
    const response = await fetch(`${this.BACKEND_URL}/api/auth/generate-token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      this.logger.error({ response }, "Phoenix pixel: Failed to fetch new token");
      throw new Error(`Token generation failed: ${response.status}`);
    }

    const data = await response.json();

    // Store refresh token
    sessionStorage.setItem(this.REFRESH_TOKEN_KEY, data.refresh_token);

    return {
      token: data.access_token,
      expiresIn: data.expires_in,
      shopDomain: shopDomain,
      shopStatus: "unknown", // Not in response, will be checked via JWT
      permissions: [],
    };
  }

  /**
   * Refresh token by fetching new token pair
   */
  async refreshToken(shopDomain, customerId = null) {
    if (this.refreshPromise) {
      try {
        return (await this.refreshPromise).token;
      } catch (error) {
        return null;
      }
    }

    this.refreshPromise = this.fetchNewTokenPair(shopDomain, customerId);

    try {
      const tokenInfo = await this.refreshPromise;
      this.storeToken(tokenInfo);
      return tokenInfo.token;
    } catch (error) {
      this.logger.error({ error }, "Phoenix pixel: Failed to refresh token");
      return null;
    } finally {
      this.refreshPromise = null;
    }
  }

  /**
   * Refresh access token using stored refresh token
   * Falls back to generating new token pair if refresh fails
   */
  async refreshAccessToken(shopDomain, customerId = null) {
    // Prevent concurrent refresh attempts
    if (this.refreshAccessTokenPromise) {
      try {
        return await this.refreshAccessTokenPromise;
      } catch (error) {
        return null;
      }
    }

    this.refreshAccessTokenPromise = (async () => {
      try {
        // Get stored refresh token
        const storedRefreshToken = sessionStorage.getItem(this.REFRESH_TOKEN_KEY);

        if (!storedRefreshToken) {
          this.logger.warn(
            "Phoenix pixel: No refresh token found, generating new token pair",
          );
          // Fallback to generating new token pair
          return await this.refreshToken(shopDomain, customerId);
        }

        // Try to refresh using refresh token
        const response = await fetch(`${this.BACKEND_URL}/api/auth/refresh-token`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: storedRefreshToken }),
        });

        if (response.ok) {
          const data = await response.json();

          // Store new tokens
          const tokenInfo = {
            token: data.access_token,
            expiresIn: data.expires_in,
            shopDomain: shopDomain,
            shopStatus: "unknown",
            permissions: [],
          };
          this.storeToken(tokenInfo);

          // Update refresh token if provided (only when regenerated)
          if (data.refresh_token) {
            sessionStorage.setItem(this.REFRESH_TOKEN_KEY, data.refresh_token);
          }

          this.logger.info("Phoenix pixel: Access token refreshed successfully");
          return tokenInfo.token;
        } else {
          // Refresh token expired or invalid - fallback to new token pair
          this.logger.warn(
            "Phoenix pixel: Refresh token failed, generating new token pair",
          );
          sessionStorage.removeItem(this.REFRESH_TOKEN_KEY);
          return await this.refreshToken(shopDomain, customerId);
        }
      } catch (error) {
        this.logger.error({ error }, "Phoenix pixel: Failed to refresh access token");
        // Fallback to generating new token pair
        return await this.refreshToken(shopDomain, customerId);
      }
    })();

    try {
      return await this.refreshAccessTokenPromise;
    } finally {
      this.refreshAccessTokenPromise = null;
    }
  }

  /**
   * Get valid token (check storage first, fetch if needed)
   */
  async getValidToken(shopDomain, customerId = null) {
    const storedToken = this.getStoredToken();

    if (
      storedToken &&
      storedToken.token &&
      storedToken.shopDomain === shopDomain &&
      this.isTokenNotExpired(storedToken)
    ) {
      return storedToken.token;
    }

    try {
      return await this.refreshToken(shopDomain, customerId);
    } catch (error) {
      this.logger.error({ error }, "Phoenix pixel: Failed to get valid token");
      return null;
    }
  }

  /**
   * Make authenticated request with automatic token refresh on 401 and retry on failures
   *
   * This acts as a "fetch interceptor" - wrapping fetch calls to:
   * 1. Add Authorization header (request interceptor)
   * 2. Handle 401 responses and retry with fresh token (response interceptor)
   * 3. Retry on network errors and 5xx server errors
   *
   * Unlike axios, native fetch has no built-in interceptors, so we use wrapper functions.
   * All API calls should use this method instead of direct fetch().
   */
  async makeAuthenticatedRequest(url, options = {}) {
    // Check initialization if shopDomain not provided
    const { shopDomain, customerId, ...fetchOptions } = options;
    const requestShopDomain = shopDomain || this.shopDomain;

    if (!requestShopDomain) {
      if (!this.isInitialized) {
        return new Response(JSON.stringify({ error: 'Not initialized' }), { status: 500 });
      }
      throw new Error("shopDomain is required for authenticated requests");
    }

    if (!this.isInitialized) {
      return new Response(JSON.stringify({ error: 'Not initialized' }), { status: 500 });
    }

    const MAX_RETRIES = 3;
    let lastError = null;

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        // Get valid token (proactive refresh)
        let token = await this.getValidToken(requestShopDomain, customerId);

        if (!token) {
          throw new Error("No valid JWT token available");
        }

        // Make request
        let response = await fetch(url, {
          ...fetchOptions,
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
            ...fetchOptions.headers,
          },
        });

        // ✅ Handle 401: Refresh token and retry once
        if (response.status === 401 && attempt === 0) {
          this.logger.warn("Phoenix pixel: Received 401, attempting token refresh");

          const newToken = await this.refreshAccessToken(requestShopDomain, customerId);

          if (newToken) {
            // Retry with new token (don't count as retry attempt)
            response = await fetch(url, {
              ...fetchOptions,
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${newToken}`,
                ...fetchOptions.headers,
              },
            });
          } else {
            this.logger.error("Phoenix pixel: Token refresh failed");
            return response; // Return 401 response
          }
        }

        // ✅ Retry on 5xx server errors (transient failures)
        if (response.status >= 500 && response.status < 600) {
          if (attempt < MAX_RETRIES - 1) {
            const delay = Math.min(500 * Math.pow(2, attempt), 2000); // Exponential backoff: 500ms, 1000ms, 2000ms
            this.logger.warn(
              `Phoenix pixel: Server error ${response.status}, retrying in ${delay}ms (attempt ${attempt + 1}/${MAX_RETRIES})`,
            );
            await new Promise((resolve) => setTimeout(resolve, delay));
            continue; // Retry
          }
        }

        // ✅ Retry on 429 rate limiting
        if (response.status === 429 && attempt < MAX_RETRIES - 1) {
          // Get retry-after header if available, otherwise use exponential backoff
          const retryAfter = response.headers.get("Retry-After");
          const delay = retryAfter
            ? parseInt(retryAfter, 10) * 1000
            : Math.min(1000 * Math.pow(2, attempt), 5000); // 1s, 2s, 5s max
          this.logger.warn(
            `Phoenix pixel: Rate limited (429), retrying in ${delay}ms (attempt ${attempt + 1}/${MAX_RETRIES})`,
          );
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue; // Retry
        }

        // Success or non-retryable error (4xx except 401/429)
        return response;
      } catch (error) {
        lastError = error;

        // ✅ Retry on network errors (offline, timeout, connection refused)
        if (attempt < MAX_RETRIES - 1) {
          const delay = Math.min(500 * Math.pow(2, attempt), 2000); // Exponential backoff
          this.logger.warn(
            `Phoenix pixel: Network error (${error?.message || "unknown"}), retrying in ${delay}ms (attempt ${attempt + 1}/${MAX_RETRIES})`,
          );
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue; // Retry
        }

        // Max retries reached, throw error
        throw error;
      }
    }

    // Should never reach here, but TypeScript needs it
    if (lastError) {
      throw lastError;
    }
    throw new Error("Request failed after max retries");
  }

  /**
   * Clear stored token
   */
  clearToken() {
    try {
      sessionStorage.removeItem(this.TOKEN_KEY);
      sessionStorage.removeItem(this.TOKEN_EXPIRY_KEY);
      sessionStorage.removeItem(this.SHOP_DOMAIN_KEY);
      sessionStorage.removeItem(this.REFRESH_TOKEN_KEY);
    } catch (error) {
      this.logger.error({ error }, "Phoenix pixel: Failed to clear token");
    }
  }
}

// Export for use in Phoenix
window.JWTTokenManager = JWTTokenManager;