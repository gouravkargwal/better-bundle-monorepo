// Unified Analytics API endpoints
const UNIFIED_ANALYTICS_BASE_URL = "https://d242bda5e5c7.ngrok-free.app";

// Session management
let currentSessionId: string | null = null;
let sessionExpiresAt: number | null = null;

/**
 * Get or create a session for Atlas tracking
 */
export const getOrCreateSession = async (
  shopDomain: string,
  userAgent: string,
  customerId: string | null,
  pageUrl: string,
  referrer: string,
  sessionStorage: any,
): Promise<string> => {
  // Check if we have a valid session
  if (currentSessionId && sessionExpiresAt && Date.now() < sessionExpiresAt) {
    return currentSessionId;
  }

  try {
    const url = `${UNIFIED_ANALYTICS_BASE_URL}/api/atlas/get-or-create-session`;

    const payload = {
      shop_domain: shopDomain,
      customer_id: customerId,
      browser_session_id: await getBrowserSessionId(sessionStorage),
      user_agent: userAgent,
      ip_address: null, // Will be detected server-side
      referrer: referrer,
      page_url: pageUrl,
    };

    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      keepalive: true,
    });

    if (!response.ok) {
      throw new Error(`Session creation failed: ${response.status}`);
    }

    const result = await response.json();

    if (result.success && result.data && result.data.session_id) {
      const sessionId = result.data.session_id;
      currentSessionId = sessionId;
      // Set session to expire 30 minutes from now (server handles actual expiration)
      sessionExpiresAt = Date.now() + 30 * 60 * 1000;

      return sessionId;
    } else {
      throw new Error(result.message || "Failed to create session");
    }
  } catch (error) {
    throw error;
  }
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
    const sessionId = await getOrCreateSession(
      shopDomain,
      userAgent,
      customerId,
      pageUrl,
      referrer,
      sessionStorage,
    );

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
    const url = `${UNIFIED_ANALYTICS_BASE_URL}/api/atlas/track-interaction`;

    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(interactionData),
      keepalive: true,
    });

    if (!response.ok) {
      throw new Error(`Interaction tracking failed: ${response.status}`);
    }
    await response.json();
  } catch (error) {
    throw error;
  }
};

/**
 * Get unified browser session ID (shared across all extensions)
 */
const getBrowserSessionId = async (sessionStorage: any): Promise<string> => {
  let sessionId = await sessionStorage.getItem("unified_browser_session_id");
  if (!sessionId) {
    sessionId =
      "unified_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
    await sessionStorage.setItem("unified_browser_session_id", sessionId);
  }
  return sessionId;
};

export const trackLoad = async (
  shopDomain: string,
  localStorage: any,
  pageUrl: string,
) => {
  try {
    const extensionUid = "atlas-web-pixel-001";
    const now = Date.now();
    const lastReported = localStorage.getItem(
      `ext_${extensionUid}_last_reported`,
    )
      ? parseInt(localStorage.getItem(`ext_${extensionUid}_last_reported`))
      : null;

    const hoursSinceLastReport = lastReported
      ? (now - lastReported) / (1000 * 60 * 60)
      : Infinity;

    // Only call API if haven't reported in last 24 hours
    if (!lastReported || hoursSinceLastReport > 24) {
      await reportToAPI(shopDomain, extensionUid, pageUrl);
      localStorage.setItem(`ext_${extensionUid}_last_reported`, now.toString());
    }
  } catch (error) {
    throw error;
  }
};
const reportToAPI = async (
  shopDomain: string,
  extensionUid: string,
  pageUrl: string,
) => {
  try {
    const requestBody = {
      extension_type: "atlas",
      extension_uid: extensionUid,
      page_url: pageUrl,
      app_block_target: null,
      app_block_location: null,
      shop_domain: shopDomain,
    };

    const response = await fetch(
      `${UNIFIED_ANALYTICS_BASE_URL}/extension-activity/track-load`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(requestBody),
      },
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        `HTTP error! status: ${response.status}, body: ${errorText}`,
      );
    }

    await response.json();
  } catch (error: any) {
    throw error;
  }
};
