import { BACKEND_URL, STORAGE_KEYS } from "../config/constants";
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

// JWT Token Storage Keys (using constants)
const TOKEN_KEY = STORAGE_KEYS.JWT_TOKEN;
const REFRESH_TOKEN_KEY = STORAGE_KEYS.JWT_REFRESH_TOKEN;
const TOKEN_EXPIRY_KEY = STORAGE_KEYS.JWT_TOKEN_EXPIRY;
const SHOP_DOMAIN_KEY = STORAGE_KEYS.SHOP_DOMAIN;

// Module-level promises for preventing concurrent refresh attempts
let refreshPromise: Promise<TokenInfo> | null = null;
let refreshAccessTokenPromise: Promise<string | null> | null = null;

/**
 * Check if token is still valid (not expired)
 */
const isTokenNotExpired = (tokenInfo: TokenInfo): boolean => {
  if (!tokenInfo || !tokenInfo.expiresIn) return false;
  const now = Date.now() / 1000;
  const expiry = tokenInfo.expiresIn;
  return expiry - now > 60; // Valid if expires in more than 60 seconds
};

/**
 * Get stored token from storage
 */
const getStoredToken = async (storage): Promise<TokenInfo | null> => {
  try {
    const token = await storage.read(TOKEN_KEY);
    const shopDomain = await storage.read(SHOP_DOMAIN_KEY);

    if (!token || !shopDomain) return null;

    const expiryStr = await storage.read(TOKEN_EXPIRY_KEY);
    return {
      token,
      expiresIn: parseInt(expiryStr || "0"),
      shopDomain,
      shopStatus: "unknown",
      permissions: [],
    };
  } catch (error) {
    logger.error({ error }, "Venus pixel: Failed to get stored token");
    return null;
  }
};

/**
 * Store token information in storage
 */
const storeToken = async (storage, tokenInfo) => {
  try {
    await storage.write(TOKEN_KEY, tokenInfo.token);
    const expiryTimestamp = Math.floor(Date.now() / 1000) + tokenInfo.expiresIn;
    await storage.write(TOKEN_EXPIRY_KEY, expiryTimestamp.toString());
    await storage.write(SHOP_DOMAIN_KEY, tokenInfo.shopDomain);
  } catch (error) {
    logger.error({ error }, "Venus pixel: Failed to store token");
  }
};

/**
 * Fetch new token pair (access + refresh) from backend
 */
const fetchNewTokenPair = async (
  storage,
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
    logger.error({ response }, "Venus pixel: Failed to fetch new token");
    throw new Error(`Token generation failed: ${response.status}`);
  }

  const data: TokenPairResponse = await response.json();

  // Store refresh token
  await storage.write(REFRESH_TOKEN_KEY, data.refresh_token);

  return {
    token: data.access_token,
    expiresIn: data.expires_in,
    shopDomain: shopDomain,
    shopStatus: "unknown", // Not in response, will be checked via JWT
    permissions: [],
  };
};

/**
 * Refresh token by fetching new token pair
 */
const refreshToken = async (
  storage,
  shopDomain: string,
  customerId?: string | null,
): Promise<string | null> => {
  if (refreshPromise) {
    try {
      return (await refreshPromise).token;
    } catch (error) {
      return null;
    }
  }

  refreshPromise = fetchNewTokenPair(storage, shopDomain, customerId);

  try {
    const tokenInfo = await refreshPromise;
    await storeToken(storage, tokenInfo);
    return tokenInfo.token;
  } catch (error) {
    logger.error({ error }, "Venus pixel: Failed to refresh token");
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
  storage,
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
      // Get stored refresh token
      const storedRefreshToken = await storage.read(REFRESH_TOKEN_KEY);

      if (!storedRefreshToken) {
        logger.warn(
          "Venus pixel: No refresh token found, generating new token pair",
        );
        // Fallback to generating new token pair
        return await refreshToken(storage, shopDomain, customerId);
      }

      // Try to refresh using refresh token
      const response = await fetch(`${BACKEND_URL}/api/auth/refresh-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: storedRefreshToken }),
      });

      if (response.ok) {
        const data = await response.json();

        // Store new tokens
        const tokenInfo: TokenInfo = {
          token: data.access_token,
          expiresIn: data.expires_in,
          shopDomain: shopDomain,
          shopStatus: "unknown",
          permissions: [],
        };
        await storeToken(storage, tokenInfo);

        // Update refresh token if provided (only when regenerated)
        if (data.refresh_token) {
          await storage.write(REFRESH_TOKEN_KEY, data.refresh_token);
        }

        logger.info("Venus pixel: Access token refreshed successfully");
        return tokenInfo.token;
      } else {
        // Refresh token expired or invalid - fallback to new token pair
        logger.warn(
          "Venus pixel: Refresh token failed, generating new token pair",
        );
        await storage.delete(REFRESH_TOKEN_KEY);
        return await refreshToken(storage, shopDomain, customerId);
      }
    } catch (error) {
      logger.error({ error }, "Venus pixel: Failed to refresh access token");
      // Fallback to generating new token pair
      return await refreshToken(storage, shopDomain, customerId);
    }
  })();

  try {
    return await refreshAccessTokenPromise;
  } finally {
    refreshAccessTokenPromise = null;
  }
};

/**
 * Get valid token (check storage first, fetch if needed)
 */
const getValidToken = async (
  storage,
  shopDomain: string,
  customerId?: string | null,
): Promise<string | null> => {
  const storedToken = await getStoredToken(storage);

  if (
    storedToken &&
    storedToken.token &&
    storedToken.shopDomain === shopDomain &&
    isTokenNotExpired(storedToken)
  ) {
    return storedToken.token;
  }

  try {
    return await refreshToken(storage, shopDomain, customerId);
  } catch (error) {
    logger.error({ error }, "Venus pixel: Failed to get valid token");
    return null;
  }
};

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
export const makeAuthenticatedRequest = async (
  storage: Storage,
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
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      // Get valid token (proactive refresh)
      let token = await getValidToken(storage, shopDomain, customerId);

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
        logger.warn("Venus pixel: Received 401, attempting token refresh");

        const newToken = await refreshAccessToken(
          storage,
          shopDomain,
          customerId,
        );

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
          logger.error("Venus pixel: Token refresh failed");
          return response; // Return 401 response
        }
      }

      // ✅ Retry on 5xx server errors (transient failures)
      if (response.status >= 500 && response.status < 600) {
        if (attempt < MAX_RETRIES - 1) {
          const delay = Math.min(500 * Math.pow(2, attempt), 2000); // Exponential backoff: 500ms, 1000ms, 2000ms
          logger.warn(
            `Venus pixel: Server error ${response.status}, retrying in ${delay}ms (attempt ${attempt + 1}/${MAX_RETRIES})`,
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
        logger.warn(
          `Venus pixel: Rate limited (429), retrying in ${delay}ms (attempt ${attempt + 1}/${MAX_RETRIES})`,
        );
        await new Promise((resolve) => setTimeout(resolve, delay));
        continue; // Retry
      }

      // Success or non-retryable error (4xx except 401/429)
      return response;
    } catch (error: any) {
      lastError = error;

      // ✅ Retry on network errors (offline, timeout, connection refused)
      if (attempt < MAX_RETRIES - 1) {
        const delay = Math.min(500 * Math.pow(2, attempt), 2000); // Exponential backoff
        logger.warn(
          `Venus pixel: Network error (${error?.message || "unknown"}), retrying in ${delay}ms (attempt ${attempt + 1}/${MAX_RETRIES})`,
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
};
