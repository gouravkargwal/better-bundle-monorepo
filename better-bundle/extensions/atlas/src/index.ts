import { register } from "@shopify/web-pixels-extension";
import { SUBSCRIBABLE_EVENTS } from "./config/constants";
import { trackInteraction } from "./utils/api-client";

register(({ analytics, init, browser }) => {
  // Add error handling wrapper
  const safeExecute = async (fn: () => Promise<void>, context: string) => {
    try {
      await fn();
    } catch (error) {
      console.error(`Atlas pixel error in ${context}:`, error);
    }
  };

  // Validate required data
  if (!init?.data?.shop?.myshopifyDomain) {
    console.error("Atlas pixel: Missing shop domain");
    return;
  }

  const customerId = init?.data?.customer?.id || null;
  const userAgent = init?.context?.navigator?.userAgent;
  const pageUrl = init?.context?.document?.location?.href;
  const referrer = init?.context?.document?.referrer;
  const shopDomain = init?.data?.shop?.myshopifyDomain;
  const sessionStorage = browser?.sessionStorage;
  const sendBeacon = browser?.sendBeacon;
  let clientId: string | null = null;

  console.log("Atlas pixel initialized for shop:", shopDomain); // Helper function to handle customer linking detection
  const handleCustomerLinking = async (event: any) => {
    await safeExecute(async () => {
      // Extract clientId from the event if available
      if (event?.clientId && !clientId) {
        clientId = event.clientId;

        // Send customer linking event now that we have both customerId and clientId
        // Backend will handle deduplication using database constraints
        if (customerId) {
          await trackInteraction(
            {
              name: "customer_linked",
              id: `customer_linked_${Date.now()}`,
              timestamp: new Date().toISOString(),
              customerId: customerId,
              clientId: clientId,
            },
            shopDomain,
            userAgent,
            customerId,
            "customer_linked",
            pageUrl,
            referrer,
            sessionStorage,
            sendBeacon,
          );
        }
      }
    }, "handleCustomerLinking");
  };

  // Helper function to extract and store attribution from URL
  const extractAndStoreAttribution = async (event: any) => {
    await safeExecute(async () => {
      // Get URL from event context (official Shopify Web Pixels API)
      const url = event?.context?.document?.location?.href;

      if (!url) {
        console.warn("Atlas pixel: No URL found in event context");
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
      console.warn("Atlas pixel: Failed to get stored attribution:", error);
    }
    return null;
  };

  // Helper function to enhance events with customer ID and attribution
  const enhanceEventWithCustomerId = async (event: any) => {
    try {
      const attributionData = await getStoredAttribution();

      return {
        ...event,
        ...(customerId && { customerId }),
        ...(attributionData && {
          ref: attributionData.ref,
          src: attributionData.src,
          pos: attributionData.pos,
        }),
      };
    } catch (error) {
      console.warn("Atlas pixel: Failed to enhance event:", error);
      return event; // Return original event if enhancement fails
    }
  };

  // Helper function to create event handlers with error handling
  const createEventHandler = (eventType: string) => {
    return async (event: any) => {
      await safeExecute(async () => {
        // Handle customer linking detection (only on first event with clientId)
        await handleCustomerLinking(event);

        const enhancedEvent = await enhanceEventWithCustomerId(event);
        await trackInteraction(
          enhancedEvent,
          shopDomain,
          userAgent,
          customerId,
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

      // Handle customer linking detection (only on first event with clientId)
      await handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);

      // Use new unified tracking system
      await trackInteraction(
        enhancedEvent,
        shopDomain,
        userAgent,
        customerId,
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
