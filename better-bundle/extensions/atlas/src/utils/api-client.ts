// Unified Analytics API endpoints
const UNIFIED_ANALYTICS_BASE_URL = "https://036cff6f721b.ngrok-free.app";

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
  clientId: string,
): Promise<string> => {
  // Check if we have a valid session in sessionStorage (unified across all extensions)
  const storedSessionId = await sessionStorage.getItem("unified_session_id");
  const storedExpiresAt = await sessionStorage.getItem(
    "unified_session_expires_at",
  );

  if (
    storedSessionId &&
    storedExpiresAt &&
    Date.now() < parseInt(storedExpiresAt)
  ) {
    return storedSessionId;
  }

  try {
    const url = `${UNIFIED_ANALYTICS_BASE_URL}/api/atlas/get-or-create-session`;

    const payload = {
      shop_domain: shopDomain,
      customer_id: customerId,
      browser_session_id: clientId,
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
      const expiresAt = Date.now() + 30 * 60 * 1000; // 30 minutes from now

      // Store session data in sessionStorage for persistence (unified across all extensions)
      await sessionStorage.setItem("unified_session_id", sessionId);
      await sessionStorage.setItem(
        "unified_session_expires_at",
        expiresAt.toString(),
      );

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
