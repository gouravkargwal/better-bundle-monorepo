import { useState, useEffect, useCallback } from "react";
import { useApi } from "@shopify/ui-extensions-react/customer-account";
import { BACKEND_URL } from "../constant";
import { logger } from "../utils/logger";

interface TokenInfo {
  token: string;
  expiresIn: number;
  shopDomain: string;
  shopStatus: string;
  permissions: string[];
}

export function useJWT(shopDomain?: string, customerId?: string) {
  const { storage } = useApi();
  const [token, setToken] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);

  const TOKEN_KEY = "betterbundle_jwt_token";
  const TOKEN_EXPIRY_KEY = "betterbundle_jwt_expiry";
  const SHOP_DOMAIN_KEY = "betterbundle_shop_domain";

  // Check if token is not expired
  const isTokenNotExpired = (tokenInfo: TokenInfo): boolean => {
    if (!tokenInfo || !tokenInfo.expiresIn) return false;
    const now = Date.now() / 1000;
    const expiry = tokenInfo.expiresIn;
    return expiry - now > 60; // Valid if expires in more than 1 minute
  };

  // Get stored token from Shopify storage
  const getStoredToken = async (): Promise<TokenInfo | null> => {
    try {
      const token = await storage.read<string>(TOKEN_KEY);
      const shopDomain = await storage.read<string>(SHOP_DOMAIN_KEY);

      if (!token || !shopDomain) return null;

      return {
        token,
        expiresIn: parseInt(
          (await storage.read<string>(TOKEN_EXPIRY_KEY)) || "0",
        ),
        shopDomain,
        shopStatus: "unknown",
        permissions: [],
      };
    } catch (error) {
      return null;
    }
  };

  // Store token in Shopify storage
  const storeToken = async (tokenInfo: TokenInfo): Promise<void> => {
    try {
      await storage.write(TOKEN_KEY, tokenInfo.token);
      const expiryTimestamp =
        Math.floor(Date.now() / 1000) + tokenInfo.expiresIn;
      await storage.write(TOKEN_EXPIRY_KEY, expiryTimestamp.toString());
      await storage.write(SHOP_DOMAIN_KEY, tokenInfo.shopDomain);
    } catch (error) {
      // Silently fail
    }
  };

  // Fetch new token from backend
  const fetchNewToken = async (
    shopDomain?: string,
    customerId?: string,
  ): Promise<TokenInfo> => {
    const requestBody: any = {};

    if (shopDomain) {
      requestBody.shop_domain = shopDomain;
    } else if (customerId) {
      requestBody.customer_id = customerId;
    } else {
      throw new Error("Either shopDomain or customerId must be provided");
    }

    const response = await fetch(`${BACKEND_URL}/api/v1/auth/shop-token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      throw new Error(`Token generation failed: ${response.status}`);
    }

    const data = await response.json();
    return {
      token: data.token,
      expiresIn: data.expires_in,
      shopDomain: data.shop_domain,
      shopStatus: data.shop_status,
      permissions: data.permissions,
    };
  };

  // Get valid token (check storage first, fetch if needed)
  const getValidToken = useCallback(
    async (
      shopDomain?: string,
      customerId?: string,
    ): Promise<string | null> => {
      try {
        const storedToken = await getStoredToken();

        // Use cached token if valid and matches current shop
        if (
          storedToken &&
          storedToken.token &&
          isTokenNotExpired(storedToken) &&
          (shopDomain ? storedToken.shopDomain === shopDomain : true)
        ) {
          return storedToken.token;
        }

        // Fetch new token
        const tokenInfo = await fetchNewToken(shopDomain, customerId);
        await storeToken(tokenInfo);
        return tokenInfo.token;
      } catch (error) {
        logger.error(
          {
            error: error instanceof Error ? error.message : String(error),
            shop_domain: shopDomain,
            customer_id: customerId,
          },
          "Failed to get JWT token",
        );
        return null;
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    [],
  );

  // Make authenticated API request
  const makeAuthenticatedRequest = async (
    url: string,
    options: RequestInit = {},
  ): Promise<Response> => {
    if (!token) {
      return new Response(JSON.stringify({ error: "No token available" }), {
        status: 401,
      });
    }

    return fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...options.headers,
      },
    });
  };

  // Initialize JWT
  useEffect(() => {
    const initializeJWT = async () => {
      if (!shopDomain && !customerId) return;

      try {
        const validToken = await getValidToken(shopDomain, customerId);
        if (validToken) {
          setToken(validToken);
          setIsReady(true);
        } else {
          setIsReady(false);
        }
      } catch (error) {
        logger.error(
          {
            error: error instanceof Error ? error.message : String(error),
            shop_domain: shopDomain,
            customer_id: customerId,
          },
          "Failed to initialize JWT",
        );
        setIsReady(false);
      }
    };

    initializeJWT();
  }, [shopDomain, customerId, getValidToken]);

  return {
    token,
    isReady,
    makeAuthenticatedRequest,
  };
}
