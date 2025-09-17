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

      console.log("🔄 Atlas session created/retrieved:", sessionId);
      return sessionId;
    } else {
      throw new Error(result.message || "Failed to create session");
    }
  } catch (error) {
    console.error("💥 Session creation error:", error);
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
    const result = await response.json();
    if (result.success) {
      console.log("✅ Atlas interaction tracked:", result.data?.interaction_id);
    } else {
      throw new Error(result.message || "Failed to track interaction");
    }
  } catch (error) {
    console.error("💥 Atlas interaction tracking error:", error);
    throw error;
  }
};

/**
 * Get browser session ID (fallback if no session exists)
 */
const getBrowserSessionId = async (sessionStorage: any): Promise<string> => {
  let sessionId = await sessionStorage.getItem("atlas_session_id");
  if (!sessionId) {
    sessionId =
      "atlas_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
    await sessionStorage.setItem("atlas_session_id", sessionId);
  }
  return sessionId;
};
