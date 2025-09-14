import { register } from "@shopify/web-pixels-extension";
import type { AtlasConfig } from "./types";
import { SUBSCRIBABLE_EVENTS } from "./config/constants";
import { sendEvent } from "./utils/api-client";

const createConfig = (settings: any, init: any): AtlasConfig => {
  return {
    backendUrl: settings.backend_url,
    shopDomain: init?.data?.shop?.myshopifyDomain,
  };
};

register(({ analytics, settings, init, browser }) => {
  const config = createConfig(settings, init);
  // Get customer ID from init object
  const customerId = init?.data?.customer?.id;
  let clientId: string | null = null; // Helper function to handle customer linking detection
  const handleCustomerLinking = (event: any) => {
    // Extract clientId from the event if available
    if (event.clientId && !clientId) {
      clientId = event.clientId;

      // Send customer linking event now that we have both customerId and clientId
      // Backend will handle deduplication using database constraints
      if (customerId) {
        sendEvent(
          {
            name: "customer_linked",
            id: `customer_linked_${Date.now()}`,
            timestamp: new Date().toISOString(),
            customerId: customerId,
            clientId: clientId,
            data: {
              customerId: customerId,
              clientId: clientId,
              linkedAt: new Date().toISOString(),
            },
          },
          config,
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
        console.log("📊 Stored attribution data:", attributionData);
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

  // Standard Shopify events
  analytics.subscribe(SUBSCRIBABLE_EVENTS.PAGE_VIEWED, async (event: any) => {
    console.log(
      "🔍 PAGE_VIEWED event received:",
      JSON.stringify(event, null, 2),
    );

    // Extract and store attribution from URL parameters
    await extractAndStoreAttribution(event);

    // Handle customer linking detection (only on first event with clientId)
    handleCustomerLinking(event);

    const enhancedEvent = await enhanceEventWithCustomerId(event);
    console.log(
      "📤 Enhanced event being sent:",
      JSON.stringify(enhancedEvent, null, 2),
    );
    await sendEvent(enhancedEvent, config);
  });
  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_ADDED_TO_CART,
    async (event: any) => {
      console.log(
        "🛒 PRODUCT_ADDED_TO_CART event received:",
        JSON.stringify(event, null, 2),
      );

      // Handle customer linking detection (only on first event with clientId)
      handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);
      console.log(
        "📤 Enhanced event being sent:",
        JSON.stringify(enhancedEvent, null, 2),
      );
      await sendEvent(enhancedEvent, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_REMOVED_FROM_CART,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);
      await sendEvent(enhancedEvent, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_VIEWED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);
      await sendEvent(enhancedEvent, config);
    },
  );

  analytics.subscribe(SUBSCRIBABLE_EVENTS.CART_VIEWED, async (event: any) => {
    // Handle customer linking detection (only on first event with clientId)
    handleCustomerLinking(event);

    const enhancedEvent = await enhanceEventWithCustomerId(event);
    await sendEvent(enhancedEvent, config);
  });

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.COLLECTION_VIEWED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);
      await sendEvent(enhancedEvent, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.SEARCH_SUBMITTED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);
      await sendEvent(enhancedEvent, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.CHECKOUT_STARTED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);
      await sendEvent(enhancedEvent, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.CHECKOUT_COMPLETED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      handleCustomerLinking(event);

      const enhancedEvent = await enhanceEventWithCustomerId(event);
      await sendEvent(enhancedEvent, config);
    },
  );
});
