/**
 * JWT Token Management for Apollo Extension
 * Uses storage API to persist tokens across the post-purchase session
 */

import { BACKEND_URL } from "../config/constants";
import { logger } from "./logger";

export interface TokenInfo {
  token: string;
  expiresIn: number;
  shopDomain: string;
  shopStatus: string;
  permissions: string[];
}

interface TokenPairResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  needs_refresh: boolean;
}

// Storage keys for JWT tokens in storage API
const STORAGE_KEY_TOKEN = "bb_jwt_access_token";
const STORAGE_KEY_REFRESH_TOKEN = "bb_jwt_refresh_token";
const STORAGE_KEY_TOKEN_EXPIRY = "bb_jwt_token_expiry";
const STORAGE_KEY_SHOP_DOMAIN = "bb_jwt_shop_domain";

// Module-level storage reference (set during initialization)
let storageInstance: any = null;

// Module-level promises for preventing concurrent refresh attempts
let refreshPromise: Promise<TokenInfo> | null = null;
let refreshAccessTokenPromise: Promise<string | null> | null = null;

// Module-level cache for current token
let currentToken: {
  token?: string;
  expiresIn?: number;
  shopDomain?: string;
  refreshToken?: string;
} = {};

/**
 * Initialize storage reference for token persistence
 */
export const initializeJWTStorage = (storage: any) => {
  storageInstance = storage;
};

const getStorage = (): any => {
  return storageInstance;
};

/**
 * Get stored token - check module variable first, then storage.initialData
 */
export const getStoredTokenSync = (): {
  token?: string;
  expiresIn?: number;
  shopDomain?: string;
  refreshToken?: string;
} | null => {
  if (currentToken.token && currentToken.expiresIn && currentToken.shopDomain) {
    return currentToken;
  }
  return getStoredToken();
};

/**
 * Get stored token from storage.initialData (for App component)
 */
const getStoredToken = (): {
  token?: string;
  expiresIn?: number;
  shopDomain?: string;
  refreshToken?: string;
} | null => {
  const storage = getStorage();
  if (!storage) return null;

  try {
    const storedData = storage.initialData || {};
    const token = storedData[STORAGE_KEY_TOKEN];
    const expiresIn = storedData[STORAGE_KEY_TOKEN_EXPIRY];
    const shopDomain = storedData[STORAGE_KEY_SHOP_DOMAIN];
    const refreshToken = storedData[STORAGE_KEY_REFRESH_TOKEN];

    if (token && expiresIn && shopDomain) {
      return {
        token,
        expiresIn:
          typeof expiresIn === "string" ? parseInt(expiresIn, 10) : expiresIn,
        shopDomain,
        refreshToken,
      };
    }
    return null;
  } catch (error) {
    logger.error({ error }, "Apollo: Failed to read token from storage");
    return null;
  }
};

/**
 * Store token in storage
 */
const storeToken = async (
  token: string,
  expiresIn: number,
  shopDomain: string,
  refreshToken?: string,
): Promise<void> => {
  const storage = getStorage();
  if (!storage) return;

  try {
    await storage.update({
      [STORAGE_KEY_TOKEN]: token,
      [STORAGE_KEY_TOKEN_EXPIRY]: expiresIn,
      [STORAGE_KEY_SHOP_DOMAIN]: shopDomain,
      ...(refreshToken && { [STORAGE_KEY_REFRESH_TOKEN]: refreshToken }),
    });
  } catch (error) {
    logger.error({ error }, "Apollo: Failed to store token in storage");
  }
};

/**
 * Check if token is not expired (valid if expires in more than 60 seconds)
 */
const isTokenNotExpired = (tokenInfo: { expiresIn: number }): boolean => {
  if (!tokenInfo || !tokenInfo.expiresIn) return false;
  const now = Math.floor(Date.now() / 1000);
  const expiry = tokenInfo.expiresIn;
  return expiry - now > 60; // Valid if expires in more than 60 seconds
};

/**
 * Fetch new token pair (access + refresh) from backend
 */
const fetchNewTokenPair = async (
  shopDomain: string,
  customerId?: string | null,
): Promise<TokenInfo> => {
  const requestBody: any = { shop_domain: shopDomain };

  if (customerId) {
    requestBody.customer_id = customerId;
  }

  // Use new unified endpoint
  const response = await fetch(`${BACKEND_URL}/api/auth/generate-token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    logger.error({ response }, "Apollo: Failed to fetch new token");
    throw new Error(`Token generation failed: ${response.status}`);
  }

  const data: TokenPairResponse = await response.json();

  // Ensure expires_in is a number (convert if string)
  const expiresIn =
    typeof data.expires_in === "string"
      ? parseInt(data.expires_in, 10)
      : data.expires_in;

  // Store refresh token in module variable immediately
  if (data.refresh_token) {
    currentToken.refreshToken = data.refresh_token;
  }

  return {
    token: data.access_token,
    expiresIn: expiresIn,
    shopDomain: shopDomain,
    shopStatus: "unknown", // Not in response, will be checked via JWT
    permissions: [],
  };
};

/**
 * Refresh token by fetching new token pair
 */
const refreshToken = async (
  shopDomain: string,
  customerId?: string | null,
): Promise<string | null> => {
  // Prevent concurrent refresh attempts
  if (refreshPromise) {
    try {
      const tokenInfo = await refreshPromise;
      return tokenInfo.token;
    } catch (error) {
      return null;
    }
  }

  refreshPromise = fetchNewTokenPair(shopDomain, customerId);

  try {
    const tokenInfo = await refreshPromise;

    // Store token in storage (same as recommendations/sessionId)
    // expiresIn from API is a duration (seconds), convert to timestamp
    const now = Math.floor(Date.now() / 1000);
    const expiryTimestamp = now + tokenInfo.expiresIn;

    // Get refresh token from current cache or storage
    const refreshToken =
      currentToken.refreshToken || getStoredToken()?.refreshToken;

    // Update module variable (simple, fast access)
    currentToken = {
      token: tokenInfo.token,
      expiresIn: expiryTimestamp,
      shopDomain: tokenInfo.shopDomain,
      refreshToken: refreshToken,
    };

    // Store in storage API (persists across calls)
    await storeToken(
      tokenInfo.token,
      expiryTimestamp,
      tokenInfo.shopDomain,
      refreshToken,
    );

    return tokenInfo.token;
  } catch (error) {
    logger.error({ error }, "Apollo: Error in refreshToken");
    return null;
  } finally {
    refreshPromise = null;
  }
};

/**
 * Refresh access token using stored refresh token
 * Falls back to generating new token pair if refresh fails
 */
const refreshAccessToken = async (
  shopDomain: string,
  customerId?: string | null,
): Promise<string | null> => {
  // Prevent concurrent refresh attempts
  if (refreshAccessTokenPromise) {
    try {
      return await refreshAccessTokenPromise;
    } catch (error) {
      return null;
    }
  }

  refreshAccessTokenPromise = (async (): Promise<string | null> => {
    try {
      // Get stored refresh token from storage (same as recommendations)
      const storedToken = getStoredToken();
      const storedRefreshToken = storedToken?.refreshToken;

      if (!storedRefreshToken) {
        return await refreshToken(shopDomain, customerId);
      }

      // Try to refresh using refresh token
      const response = await fetch(`${BACKEND_URL}/api/auth/refresh-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: storedRefreshToken }),
      });

      if (response.ok) {
        const data = await response.json();

        // Ensure expires_in is a number (convert if string)
        const expiresIn =
          typeof data.expires_in === "string"
            ? parseInt(data.expires_in, 10)
            : data.expires_in;

        // Update storage with new tokens (same as recommendations)
        // expires_in from API is a duration (seconds), convert to timestamp
        const now = Math.floor(Date.now() / 1000);
        const expiryTimestamp = now + expiresIn;
        const refreshToken = data.refresh_token || storedRefreshToken;

        // Update module variable
        currentToken = {
          token: data.access_token,
          expiresIn: expiryTimestamp,
          shopDomain: shopDomain,
          refreshToken: refreshToken,
        };

        // Store in storage API (persists across calls)
        await storeToken(
          data.access_token,
          expiryTimestamp,
          shopDomain,
          refreshToken,
        );
        return data.access_token;
      } else {
        return await refreshToken(shopDomain, customerId);
      }
    } catch (error) {
      logger.error({ error }, "Apollo: Failed to refresh access token");
      // Fallback to generating new token pair
      return await refreshToken(shopDomain, customerId);
    }
  })();

  try {
    return await refreshAccessTokenPromise;
  } finally {
    refreshAccessTokenPromise = null;
  }
};

/**
 * Get valid token (same pattern as recommendations - read from storage, fetch if needed)
 */
const getValidToken = async (
  shopDomain: string,
  customerId?: string | null,
): Promise<string | null> => {
  // Check module variable first (fastest), then storage
  let storedTokenData =
    currentToken.token && currentToken.expiresIn && currentToken.shopDomain
      ? currentToken
      : getStoredToken();
  if (
    storedTokenData?.token &&
    storedTokenData.shopDomain === shopDomain &&
    storedTokenData.expiresIn &&
    isTokenNotExpired({ expiresIn: storedTokenData.expiresIn })
  ) {
    return storedTokenData.token;
  }
  try {
    return await refreshToken(shopDomain, customerId);
  } catch (error) {
    logger.error({ error }, "Apollo: Failed to get valid token");
    return null;
  }
};

/**
 * Make authenticated request with automatic token refresh on 401 and retry on failures
 */
export const makeAuthenticatedRequest = async (
  url: string,
  options: RequestInit & {
    shopDomain?: string;
    customerId?: string | null;
  } = {},
): Promise<Response> => {
  const { shopDomain, customerId, ...fetchOptions } = options;

  if (!shopDomain) {
    throw new Error("shopDomain is required for authenticated requests");
  }

  const MAX_RETRIES = 3;
  let lastError = null;

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      // Get valid token (proactive refresh)
      let token = await getValidToken(shopDomain, customerId);

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

      // Handle 401: Refresh token and retry once
      if (response.status === 401 && attempt === 0) {
        const newToken = await refreshAccessToken(shopDomain, customerId);
        if (newToken) {
          response = await fetch(url, {
            ...fetchOptions,
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${newToken}`,
              ...fetchOptions.headers,
            },
          });
        } else {
          return response;
        }
      }

      // Retry on 5xx server errors
      if (response.status >= 500 && response.status < 600) {
        if (attempt < MAX_RETRIES - 1) {
          const delay = Math.min(500 * Math.pow(2, attempt), 2000);
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue;
        }
      }

      // Handle 429 rate limiting
      if (response.status === 429) {
        const retryAfter =
          response.headers.get("Retry-After") ||
          Math.min(500 * Math.pow(2, attempt), 5000);
        const delay = parseInt(retryAfter.toString()) * 1000;

        if (attempt < MAX_RETRIES - 1) {
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue;
        }
      }

      // Success or non-retryable error - return response
      return response;
    } catch (error) {
      lastError = error;

      // Network errors - retry with exponential backoff
      if (attempt < MAX_RETRIES - 1) {
        const delay = Math.min(500 * Math.pow(2, attempt), 2000);
        await new Promise((resolve) => setTimeout(resolve, delay));
        continue;
      }

      // Max retries reached - throw error
      throw error;
    }
  }

  // Should never reach here, but just in case
  if (lastError) {
    throw lastError;
  }
  throw new Error("Request failed after max retries");
};
