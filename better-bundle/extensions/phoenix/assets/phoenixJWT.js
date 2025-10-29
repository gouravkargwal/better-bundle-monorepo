/**
 * Phoenix JWT Manager
 * Phoenix-specific wrapper for JWT token management
 */

class PhoenixJWTManager {
  constructor() {
    this.jwtManager = new JWTTokenManager();
    this.shopDomain = window.shopDomain || this.getShopDomainFromUrl();
    this.isInitialized = false;
    this.currentToken = null;
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

      // Check localStorage first - no API call if token exists and is valid
      const storedToken = this.jwtManager.getStoredToken();
      if (storedToken &&
        storedToken.token &&
        storedToken.shopDomain === this.shopDomain &&
        this.jwtManager.isTokenNotExpired(storedToken)) {

        this.currentToken = storedToken.token;
      } else {
        // Only make API call if no valid token in localStorage
        this.currentToken = await this.jwtManager.getValidToken(this.shopDomain);
        if (!this.currentToken) {
          // No token available, disable features
          this.disablePhoenixFeatures();
          return;
        }
      }

      // Skip suspension check to avoid errors
      // const isSuspended = await this.jwtManager.isShopSuspended(this.shopDomain);
      // if (isSuspended) {
      //   this.disablePhoenixFeatures();
      //   return;
      // }

      this.isInitialized = true;

    } catch (error) {
      // Silently fail and disable features
      this.disablePhoenixFeatures();
    }
  }

  /**
   * Make authenticated API request
   */
  async makeAuthenticatedRequest(url, options = {}) {
    if (!this.isInitialized || !this.currentToken) {
      return new Response(JSON.stringify({ error: 'Not initialized' }), { status: 500 });
    }

    try {
      // Use the cached token directly - no refresh needed
      return fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.currentToken}`,
          ...options.headers,
        },
      });
    } catch (error) {
      // Return error response instead of throwing
      return new Response(JSON.stringify({ error: 'Request failed' }), { status: 500 });
    }
  }

  /**
   * Ensure we have a valid token, refresh if needed
   */
  async ensureValidToken() {
    if (!this.currentToken) {
      this.currentToken = await this.jwtManager.getValidToken(this.shopDomain);
      if (!this.currentToken) {
        this.disablePhoenixFeatures();
        return;
      }
    }

    // Check if current token is still valid
    const storedToken = this.jwtManager.getStoredToken();
    if (!storedToken ||
      !this.jwtManager.isTokenNotExpired(storedToken) ||
      storedToken.shopDomain !== this.shopDomain) {

      this.currentToken = await this.jwtManager.getValidToken(this.shopDomain);
      if (!this.currentToken) {
        this.disablePhoenixFeatures();
      }
    }
  }

  /**
   * Check if shop is suspended
   */
  async isShopSuspended() {
    if (!this.isInitialized) {
      return true;
    }

    try {
      return await this.jwtManager.isShopSuspended(this.shopDomain);
    } catch (error) {
      return true;
    }
  }

  /**
   * Get valid JWT token
   */
  async getValidToken() {
    if (!this.isInitialized) {
      return null;
    }

    return this.currentToken;
  }

  /**
   * Disable Phoenix features due to suspension
   */
  disablePhoenixFeatures() {
    this.isInitialized = false;

    // Hide Phoenix UI elements
    const phoenixElements = document.querySelectorAll('[data-phoenix]');
    phoenixElements.forEach(element => {
      element.style.display = 'none';
    });

    // Hide recommendation carousels
    const carouselElements = document.querySelectorAll('.shopify-app-block');
    carouselElements.forEach(element => {
      element.style.display = 'none';
    });

    // Don't show suspension message to users
  }

  /**
   * Handle initialization error
   */
  handleInitializationError(error) {
    this.disablePhoenixFeatures();
  }

  /**
   * Get shop domain from URL
   */
  getShopDomainFromUrl() {
    if (typeof window !== 'undefined' && window.location) {
      const hostname = window.location.hostname;
      if (hostname.includes('.myshopify.com')) {
        return hostname.replace('.myshopify.com', '');
      }
    }
    return null;
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
   * Clear JWT token
   */
  clearToken() {
    this.jwtManager.clearToken();
  }
}

// Export for use in other Phoenix files
window.PhoenixJWT = PhoenixJWTManager;
