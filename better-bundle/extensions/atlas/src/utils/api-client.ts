import { BACKEND_URL } from "../config/constants";
import { logger } from "./logger";

interface TokenInfo {
  token: string;
  expiresIn: number;
  shopDomain: string;
  shopStatus: string;
  permissions: string[];
}

class JWTManager {
  private TOKEN_KEY = "betterbundle_jwt_token";
  private TOKEN_EXPIRY_KEY = "betterbundle_jwt_expiry";
  private SHOP_DOMAIN_KEY = "betterbundle_shop_domain";
  private refreshPromise: Promise<TokenInfo> | null = null;

  constructor(private sessionStorage: any) {}

  async getValidToken(
    shopDomain: string,
    customerId?: string | null,
  ): Promise<string | null> {
    const storedToken = await this.getStoredToken();

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
      logger.error({ error }, "Atlas pixel: Failed to get valid token");
      return null;
    }
  }

  private async refreshToken(
    shopDomain: string,
    customerId?: string | null,
  ): Promise<string | null> {
    if (this.refreshPromise) {
      try {
        return (await this.refreshPromise).token;
      } catch (error) {
        return null;
      }
    }

    this.refreshPromise = this.fetchNewToken(shopDomain, customerId);

    try {
      const tokenInfo = await this.refreshPromise;
      await this.storeToken(tokenInfo);
      return tokenInfo.token;
    } catch (error) {
      logger.error({ error }, "Atlas pixel: Failed to refresh token");
      return null;
    } finally {
      this.refreshPromise = null;
    }
  }

  private async fetchNewToken(
    shopDomain: string,
    customerId?: string | null,
  ): Promise<TokenInfo> {
    const requestBody: any = { shop_domain: shopDomain };

    if (customerId) {
      requestBody.customer_id = customerId;
    }

    const response = await fetch(`${BACKEND_URL}/api/v1/auth/shop-token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      logger.error({ response }, "Atlas pixel: Failed to fetch new token");
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
  }

  private isTokenNotExpired(tokenInfo: TokenInfo): boolean {
    if (!tokenInfo || !tokenInfo.expiresIn) return false;
    const now = Date.now() / 1000;
    const expiry = tokenInfo.expiresIn;
    return expiry - now > 60;
  }

  private async getStoredToken(): Promise<TokenInfo | null> {
    try {
      const token = await this.sessionStorage.getItem(this.TOKEN_KEY);
      const shopDomain = await this.sessionStorage.getItem(
        this.SHOP_DOMAIN_KEY,
      );

      if (!token || !shopDomain) return null;

      return {
        token,
        expiresIn: parseInt(
          (await this.sessionStorage.getItem(this.TOKEN_EXPIRY_KEY)) || "0",
        ),
        shopDomain,
        shopStatus: "unknown",
        permissions: [],
      };
    } catch (error) {
      logger.error({ error }, "Atlas pixel: Failed to get stored token");
      return null;
    }
  }

  private async storeToken(tokenInfo: TokenInfo): Promise<void> {
    try {
      await this.sessionStorage.setItem(this.TOKEN_KEY, tokenInfo.token);
      const expiryTimestamp =
        Math.floor(Date.now() / 1000) + tokenInfo.expiresIn;
      await this.sessionStorage.setItem(
        this.TOKEN_EXPIRY_KEY,
        expiryTimestamp.toString(),
      );
      await this.sessionStorage.setItem(
        this.SHOP_DOMAIN_KEY,
        tokenInfo.shopDomain,
      );
    } catch (error) {
      logger.error({ error }, "Atlas pixel: Failed to store token");
    }
  }

  async makeAuthenticatedRequest(
    url: string,
    options: RequestInit = {},
  ): Promise<Response> {
    return fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
  }
}

const getBrowserSessionId = async (sessionStorage: any): Promise<string> => {
  let sessionId = await sessionStorage.getItem("unified_browser_session_id");
  if (!sessionId) {
    sessionId =
      "unified_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
    await sessionStorage.setItem("unified_browser_session_id", sessionId);
  }
  return sessionId;
};

const getOrStoreClientId = async (
  sessionStorage: any,
  clientId: string | null,
): Promise<string | null> => {
  let storedClientId = await sessionStorage.getItem("unified_client_id");

  if (clientId && clientId !== storedClientId) {
    await sessionStorage.setItem("unified_client_id", clientId);
    return clientId;
  }

  return storedClientId || clientId;
};

let sessionCreationPromise: Promise<string> | null = null;

export const getOrCreateSession = async (
  shopDomain: string,
  userAgent: string,
  customerId: string | null,
  pageUrl: string,
  referrer: string,
  sessionStorage: any,
  clientId: string,
): Promise<string> => {
  const storedClientId = await getOrStoreClientId(sessionStorage, clientId);

  const storedSessionId = await sessionStorage.getItem("unified_session_id");
  const storedExpiresAt = await sessionStorage.getItem(
    "unified_session_expires_at",
  );

  if (
    storedSessionId &&
    storedExpiresAt &&
    Date.now() < parseInt(storedExpiresAt)
  ) {
    if (clientId && clientId !== storedClientId) {
      updateClientIdInBackground(
        storedSessionId,
        clientId,
        shopDomain,
        sessionStorage,
        customerId,
      ).catch((err) => {
        logger.error(
          { err },
          "Atlas pixel: Failed to update client_id in background",
        );
      });
    }

    return storedSessionId;
  }

  if (sessionCreationPromise) {
    return await sessionCreationPromise;
  }

  sessionCreationPromise = (async () => {
    try {
      const jwtManager = new JWTManager(sessionStorage);
      const token = await jwtManager.getValidToken(shopDomain, customerId);

      const url = `${BACKEND_URL}/api/atlas/get-or-create-session`;
      const browserSessionId = await getBrowserSessionId(sessionStorage);

      const payload = {
        shop_domain: shopDomain,
        customer_id: customerId,
        browser_session_id: browserSessionId,
        client_id: storedClientId || clientId,
        user_agent: userAgent,
        ip_address: null,
        referrer: referrer,
        page_url: pageUrl,
      };

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify(payload),
        keepalive: true,
      });

      if (!response.ok) {
        if (response.status === 403) {
          logger.error({ response }, "Atlas pixel: Services suspended");
          throw new Error("Services suspended");
        }
        logger.error({ response }, "Atlas pixel: Session creation failed");
        throw new Error(`Session creation failed: ${response.status}`);
      }

      const result = await response.json();

      if (result.success && result.data && result.data.session_id) {
        const sessionId = result.data.session_id;
        const expiresAt = Date.now() + 30 * 60 * 1000; // 30 minutes from now

        await sessionStorage.setItem("unified_session_id", sessionId);
        await sessionStorage.setItem(
          "unified_session_expires_at",
          expiresAt.toString(),
        );

        if (result.data.client_id) {
          await sessionStorage.setItem(
            "unified_client_id",
            result.data.client_id,
          );
        }

        return sessionId;
      } else {
        logger.error({ result }, "Atlas pixel: Failed to create session");
        throw new Error(result.message || "Failed to create session");
      }
    } catch (error) {
      logger.error({ error }, "Atlas pixel: Failed to create session");
      throw error;
    } finally {
      sessionCreationPromise = null;
    }
  })();
  return await sessionCreationPromise;
};

/**
 * Track interaction using unified analytics
 */
export const trackInteraction = async (
  event: any,
  shopDomain: string,
  userAgent: string,
  customerId: string | null,
  interactionType: string,
  pageUrl: string,
  referrer: string,
  sessionStorage: any,
  sendBeacon: any,
): Promise<void> => {
  try {
    const clientId = event?.clientId || null;

    const sessionId = await getOrCreateSession(
      shopDomain,
      userAgent,
      customerId,
      pageUrl,
      referrer,
      sessionStorage,
      clientId,
    );

    const jwtManager = new JWTManager(sessionStorage);
    const token = await jwtManager.getValidToken(shopDomain, customerId);

    const interactionData = {
      session_id: sessionId,
      shop_domain: shopDomain,
      customer_id: customerId,
      interaction_type: interactionType,
      metadata: {
        ...event,
      },
    };

    // Send to unified analytics endpoint
    const url = `${BACKEND_URL}/api/atlas/track-interaction`;

    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: JSON.stringify(interactionData),
      keepalive: true,
    });

    if (!response.ok) {
      if (response.status === 403) {
        logger.error({ response }, "Atlas pixel: Services suspended");
        throw new Error("Services suspended");
      }
      logger.error({ response }, "Atlas pixel: Interaction tracking failed");
      throw new Error(`Interaction tracking failed: ${response.status}`);
    }

    const result = await response.json();

    // Handle session recovery if it occurred
    if (result.session_recovery) {
      // Update stored session ID with the new one (unified with other extensions)
      await sessionStorage.setItem(
        "unified_session_id",
        result.session_recovery.new_session_id,
      );
    }
  } catch (error) {
    logger.error({ error }, "Atlas pixel: Failed to track interaction");
    throw error;
  }
};

const updateClientIdInBackground = async (
  sessionId: string,
  clientId: string,
  shopDomain: string,
  sessionStorage?: any,
  customerId?: string | null,
): Promise<void> => {
  try {
    const url = `${BACKEND_URL}/api/session/update-client-id`;

    let token: string | null = null;
    if (sessionStorage) {
      const jwtManager = new JWTManager(sessionStorage);
      token = await jwtManager.getValidToken(shopDomain, customerId);
    }

    await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: JSON.stringify({
        session_id: sessionId,
        client_id: clientId,
        shop_domain: shopDomain,
      }),
      keepalive: true,
    });
  } catch (error) {
    logger.error({ error }, "Atlas pixel: Background client_id update failed");
  }
};
