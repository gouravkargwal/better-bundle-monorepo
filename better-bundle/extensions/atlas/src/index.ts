import { register } from "@shopify/web-pixels-extension";
import { SUBSCRIBABLE_EVENTS } from "./config/constants";
import { trackInteraction, trackLoad } from "./utils/api-client";

register(({ analytics, init, browser }) => {
  const customerId = init?.data?.customer?.id || null;
  const userAgent = init?.context?.navigator?.userAgent;
  const pageUrl = init?.context?.document?.location?.href;
  const referrer = init?.context?.document?.referrer;
  const shopDomain = init?.data?.shop?.myshopifyDomain;
  const sessionStorage = browser?.sessionStorage;
  const sendBeacon = browser?.sendBeacon;
  let clientId: string | null = null; // Helper function to handle customer linking detection
  const handleCustomerLinking = async (event: any) => {
    // Extract clientId from the event if available
    if (event.clientId && !clientId) {
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
  };

  // Helper function to extract and store attribution from URL
  const extractAndStoreAttribution = async (event: any) => {
    try {
      // Get URL from event context (official Shopify Web Pixels API)
      const url = event?.context?.document?.location?.href;

      if (!url) {
        console.warn("No URL found in event context");
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

        await (browser as any).sessionStorage.setItem(
          "recommendation_attribution",
          JSON.stringify(attributionData),
        );
      }
    } catch (error) {
      console.warn("Failed to extract attribution from URL:", error);
    }
  };

  // Helper function to get stored attribution data
  const getStoredAttribution = async () => {
    try {
      const stored = await (browser as any).sessionStorage.getItem(
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
          await (browser as any).sessionStorage.removeItem(
            "recommendation_attribution",
          );
        }
      }
    } catch (error) {
      console.warn("Failed to get stored attribution:", error);
    }
    return null;
  };

  // Helper function to enhance events with customer ID and attribution
  const enhanceEventWithCustomerId = async (event: any) => {
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
  };

  // Track extension activity on first page view
  let extensionTracked = false;

  // Standard Shopify events
  analytics.subscribe(SUBSCRIBABLE_EVENTS.PAGE_VIEWED, async (event: any) => {
    // Track extension activity (only once per session, but check localStorage for throttling)
    if (!extensionTracked && shopDomain) {
      extensionTracked = true;
      trackLoad(shopDomain, browser?.localStorage, pageUrl).catch((error) => {
        console.warn("Failed to track Atlas extension activity:", error);
      });
    }

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
  });
  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_ADDED_TO_CART,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      await handleCustomerLinking(event);
      const enhancedEvent = await enhanceEventWithCustomerId(event);
      await trackInteraction(
        enhancedEvent,
        shopDomain,
        userAgent,
        customerId,
        SUBSCRIBABLE_EVENTS.PRODUCT_ADDED_TO_CART,
        pageUrl,
        referrer,
        sessionStorage,
        sendBeacon,
      );
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_REMOVED_FROM_CART,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      await handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);
      await trackInteraction(
        enhancedEvent,
        shopDomain,
        userAgent,
        customerId,
        SUBSCRIBABLE_EVENTS.PRODUCT_REMOVED_FROM_CART,
        pageUrl,
        referrer,
        sessionStorage,
        sendBeacon,
      );
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_VIEWED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      await handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);
      await trackInteraction(
        enhancedEvent,
        shopDomain,
        userAgent,
        customerId,
        SUBSCRIBABLE_EVENTS.PRODUCT_VIEWED,
        pageUrl,
        referrer,
        sessionStorage,
        sendBeacon,
      );
    },
  );

  analytics.subscribe(SUBSCRIBABLE_EVENTS.CART_VIEWED, async (event: any) => {
    // Handle customer linking detection (only on first event with clientId)
    await handleCustomerLinking(event);

    const enhancedEvent = await enhanceEventWithCustomerId(event);
    await trackInteraction(
      enhancedEvent,
      shopDomain,
      userAgent,
      customerId,
      SUBSCRIBABLE_EVENTS.CART_VIEWED,
      pageUrl,
      referrer,
      sessionStorage,
      sendBeacon,
    );
  });

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.COLLECTION_VIEWED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      await handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);
      await trackInteraction(
        enhancedEvent,
        shopDomain,
        userAgent,
        customerId,
        SUBSCRIBABLE_EVENTS.COLLECTION_VIEWED,
        pageUrl,
        referrer,
        sessionStorage,
        sendBeacon,
      );
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.SEARCH_SUBMITTED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      await handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);
      await trackInteraction(
        enhancedEvent,
        shopDomain,
        userAgent,
        customerId,
        SUBSCRIBABLE_EVENTS.SEARCH_SUBMITTED,
        pageUrl,
        referrer,
        sessionStorage,
        sendBeacon,
      );
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.CHECKOUT_STARTED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      await handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);
      await trackInteraction(
        enhancedEvent,
        shopDomain,
        userAgent,
        customerId,
        SUBSCRIBABLE_EVENTS.CHECKOUT_STARTED,
        pageUrl,
        referrer,
        sessionStorage,
        sendBeacon,
      );
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.CHECKOUT_COMPLETED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      await handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);
      await trackInteraction(
        enhancedEvent,
        shopDomain,
        userAgent,
        customerId,
        SUBSCRIBABLE_EVENTS.CHECKOUT_COMPLETED,
        pageUrl,
        referrer,
        sessionStorage,
        sendBeacon,
      );
    },
  );
});
