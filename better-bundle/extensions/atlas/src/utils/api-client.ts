import { BACKEND_URL, STORAGE_KEYS } from "../config/constants";
import { logger } from "./logger";
import { makeAuthenticatedRequest } from "./jwt";

const getBrowserSessionIdFromStorage = async (
  localStorage: any,
): Promise<string | null> => {
  return await localStorage.getItem(STORAGE_KEYS.BROWSER_SESSION_ID);
};

const storeBrowserSessionId = async (
  localStorage: any,
  browserSessionId: string,
): Promise<void> => {
  await localStorage.setItem(STORAGE_KEYS.BROWSER_SESSION_ID, browserSessionId);
};

const getOrStoreClientId = async (
  sessionStorage: any,
  clientId: string | null,
): Promise<string | null> => {
  let storedClientId = await sessionStorage.getItem(STORAGE_KEYS.CLIENT_ID);

  if (clientId && clientId !== storedClientId) {
    await sessionStorage.setItem(STORAGE_KEYS.CLIENT_ID, clientId);
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
  localStorage?: any,
): Promise<string> => {
  const storedClientId = await getOrStoreClientId(sessionStorage, clientId);

  const storedSessionId = await sessionStorage.getItem(STORAGE_KEYS.SESSION_ID);
  const storedExpiresAt = await sessionStorage.getItem(
    STORAGE_KEYS.SESSION_EXPIRES_AT,
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
      // Get browser_session_id from localStorage if available (backend-generated)
      // If not available, backend will generate it
      const storedBrowserSessionId = localStorage
        ? await getBrowserSessionIdFromStorage(localStorage)
        : null;

      const url = `${BACKEND_URL}/api/session/get-or-create-session`;

      const payload = {
        shop_domain: shopDomain,
        customer_id: customerId,
        browser_session_id: storedBrowserSessionId || undefined, // Backend will generate if not provided
        client_id: storedClientId || clientId,
        user_agent: true,
        ip_address: true,
        referrer: referrer,
        page_url: pageUrl,
        extension_type: "atlas",
      };

      // ✅ Use makeAuthenticatedRequest for automatic token refresh
      const response = await makeAuthenticatedRequest(sessionStorage, url, {
        method: "POST",
        shopDomain,
        customerId,
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

        await sessionStorage.setItem(STORAGE_KEYS.SESSION_ID, sessionId);
        await sessionStorage.setItem(
          STORAGE_KEYS.SESSION_EXPIRES_AT,
          expiresAt.toString(),
        );

        if (result.data.client_id) {
          await sessionStorage.setItem(
            STORAGE_KEYS.CLIENT_ID,
            result.data.client_id,
          );
        }

        // ✅ Store backend-generated browser_session_id in localStorage
        if (result.data.browser_session_id && localStorage) {
          await storeBrowserSessionId(
            localStorage,
            result.data.browser_session_id,
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
  localStorage?: any,
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
      localStorage,
    );

    const interactionData = {
      session_id: sessionId,
      shop_domain: shopDomain,
      extension_type: "atlas", // ✅ Add this required field
      customer_id: customerId,
      interaction_type: interactionType,
      metadata: {
        ...event,
      },
    };

    // Send to unified analytics endpoint
    const url = `${BACKEND_URL}/api/interaction/track`;

    // ✅ Use makeAuthenticatedRequest for automatic token refresh
    const response = await makeAuthenticatedRequest(sessionStorage, url, {
      method: "POST",
      shopDomain,
      customerId,
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
        STORAGE_KEYS.SESSION_ID,
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

    if (sessionStorage) {
      // ✅ Use makeAuthenticatedRequest for automatic token refresh
      await makeAuthenticatedRequest(sessionStorage, url, {
        method: "POST",
        shopDomain,
        customerId,
        body: JSON.stringify({
          session_id: sessionId,
          client_id: clientId,
          shop_domain: shopDomain,
        }),
        keepalive: true,
      });
    }
  } catch (error) {
    logger.error({ error }, "Atlas pixel: Background client_id update failed");
  }
};
