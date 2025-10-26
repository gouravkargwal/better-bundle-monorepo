import { register } from "@shopify/web-pixels-extension";
import { SUBSCRIBABLE_EVENTS } from "./config/constants";
import { trackInteraction } from "./utils/api-client";
import { logger } from "./utils/logger";

register(({ analytics, init, browser }) => {
  // Add error handling wrapper
  const safeExecute = async (fn: () => Promise<void>, context: string) => {
    try {
      await fn();
    } catch (error) {
      logger.error({ error }, `Atlas pixel error in ${context}`);
    }
  };

  // Validate required data
  if (!init?.data?.shop?.myshopifyDomain) {
    logger.error({ init }, "Atlas pixel: Missing shop domain");
    return;
  }

  const userAgent = init?.context?.navigator?.userAgent;
  const pageUrl = init?.context?.document?.location?.href;
  const referrer = init?.context?.document?.referrer;
  const shopDomain = init?.data?.shop?.myshopifyDomain;
  const sessionStorage = browser?.sessionStorage;
  const sendBeacon = browser?.sendBeacon;

  // ✅ Use an object to hold mutable state (reference type)
  const state = {
    customerId: init?.data?.customer?.id || null,
    clientId: null as string | null,
  };

  logger.info({ shopDomain, state }, "Atlas pixel initialized");

  // ✅ Helper to extract customer ID from event
  const getCustomerIdFromEvent = (event: any): string | null => {
    // Try multiple sources for customer ID
    return (
      event?.data?.checkout?.order?.customer?.id ||
      event?.data?.checkout?.customer?.id ||
      event?.customerId ||
      event?.data?.customer?.id ||
      state.customerId // Fallback to current customerId
    );
  };

  // Helper function to handle customer linking detection
  const handleCustomerLinking = async (event: any) => {
    await safeExecute(async () => {
      // Extract clientId from the event if available
      if (event?.clientId && !state.clientId) {
        state.clientId = event.clientId;
        logger.info({ state }, "Client ID detected");
      }

      // Extract customer ID from event (not just init)
      const eventCustomerId = getCustomerIdFromEvent(event);

      // Update global customerId if we found one in the event
      if (eventCustomerId && !state.customerId) {
        state.customerId = eventCustomerId;
        logger.info({ state }, "Customer ID identified from event");
      }

      // Fire customer_linked event when we have BOTH clientId and customerId
      if (state.clientId && state.customerId) {
        logger.info({ state }, "Firing customer_linked event");
        await trackInteraction(
          {
            name: "customer_linked",
            id: `customer_linked_${Date.now()}`,
            timestamp: new Date().toISOString(),
            customerId: state.customerId,
            clientId: state.clientId,
          },
          shopDomain,
          userAgent,
          state.customerId,
          "customer_linked",
          pageUrl,
          referrer,
          sessionStorage,
          sendBeacon,
        );
      }
    }, "handleCustomerLinking");
  };

  // Helper function to extract and store attribution from URL
  const extractAndStoreAttribution = async (event: any) => {
    await safeExecute(async () => {
      // Get URL from event context (official Shopify Web Pixels API)
      const url = event?.context?.document?.location?.href;

      if (!url) {
        logger.warn({ event }, "Atlas pixel: No URL found in event context");
        return;
      }

      const urlParams = new URLSearchParams(url.split("?")[1] || "");
      const ref = urlParams.get("ref");
      const src = urlParams.get("src");
      const pos = urlParams.get("pos");

      if (ref) {
        // Store attribution in session storage for the entire session
        const attributionData = {
          ref,
          src: src || "unknown",
          pos: pos || "0",
          timestamp: new Date().toISOString(),
        };

        if (browser?.sessionStorage) {
          await browser.sessionStorage.setItem(
            "recommendation_attribution",
            JSON.stringify(attributionData),
          );
        }
      }
    }, "extractAndStoreAttribution");
  };

  // Helper function to get stored attribution data
  const getStoredAttribution = async () => {
    try {
      if (!browser?.sessionStorage) {
        return null;
      }

      const stored = await browser.sessionStorage.getItem(
        "recommendation_attribution",
      );
      if (stored) {
        const attribution = JSON.parse(stored);
        // Check if attribution is still valid (within 24 hours)
        const storedTime = new Date(attribution.timestamp);
        const now = new Date();
        const hoursDiff =
          (now.getTime() - storedTime.getTime()) / (1000 * 60 * 60);

        if (hoursDiff < 24) {
          return attribution;
        } else {
          // Remove expired attribution
          await browser.sessionStorage.removeItem("recommendation_attribution");
        }
      }
    } catch (error) {
      logger.error({ error }, "Atlas pixel: Failed to get stored attribution");
    }
    return null;
  };

  // Helper function to enhance events with customer ID and attribution
  const enhanceEventWithCustomerId = async (event: any) => {
    try {
      const attributionData = await getStoredAttribution();

      return {
        ...event,
        ...(state.customerId && { customerId: state.customerId }), // ✅ Use state.customerId
        ...(attributionData && {
          ref: attributionData.ref,
          src: attributionData.src,
          pos: attributionData.pos,
        }),
      };
    } catch (error) {
      logger.error({ error, event }, "Atlas pixel: Failed to enhance event");
      return event; // Return original event if enhancement fails
    }
  };

  // Helper function to create event handlers with error handling
  const createEventHandler = (eventType: string) => {
    return async (event: any) => {
      await safeExecute(async () => {
        // Handle customer linking detection (updates state.customerId)
        await handleCustomerLinking(event);

        const enhancedEvent = await enhanceEventWithCustomerId(event);

        // ✅ Use state.customerId (always current value)
        await trackInteraction(
          enhancedEvent,
          shopDomain,
          userAgent,
          state.customerId, // ✅ Reads current value from state object
          eventType,
          pageUrl,
          referrer,
          sessionStorage,
          sendBeacon,
        );
      }, eventType);
    };
  };

  // Standard Shopify events
  analytics.subscribe(SUBSCRIBABLE_EVENTS.PAGE_VIEWED, async (event: any) => {
    await safeExecute(async () => {
      // Extract and store attribution from URL parameters
      await extractAndStoreAttribution(event);

      // Handle customer linking detection
      await handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);

      // Use new unified tracking system
      await trackInteraction(
        enhancedEvent,
        shopDomain,
        userAgent,
        state.customerId, // ✅ Use state.customerId
        SUBSCRIBABLE_EVENTS.PAGE_VIEWED,
        pageUrl,
        referrer,
        sessionStorage,
        sendBeacon,
      );
    }, "PAGE_VIEWED");
  });

  // Subscribe to all events with error handling
  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_ADDED_TO_CART,
    createEventHandler(SUBSCRIBABLE_EVENTS.PRODUCT_ADDED_TO_CART),
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_REMOVED_FROM_CART,
    createEventHandler(SUBSCRIBABLE_EVENTS.PRODUCT_REMOVED_FROM_CART),
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_VIEWED,
    createEventHandler(SUBSCRIBABLE_EVENTS.PRODUCT_VIEWED),
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.CART_VIEWED,
    createEventHandler(SUBSCRIBABLE_EVENTS.CART_VIEWED),
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.COLLECTION_VIEWED,
    createEventHandler(SUBSCRIBABLE_EVENTS.COLLECTION_VIEWED),
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.SEARCH_SUBMITTED,
    createEventHandler(SUBSCRIBABLE_EVENTS.SEARCH_SUBMITTED),
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.CHECKOUT_STARTED,
    createEventHandler(SUBSCRIBABLE_EVENTS.CHECKOUT_STARTED),
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.CHECKOUT_COMPLETED,
    createEventHandler(SUBSCRIBABLE_EVENTS.CHECKOUT_COMPLETED),
  );
});
