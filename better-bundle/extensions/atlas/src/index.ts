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

register(({ analytics, settings, init }) => {
  const config = createConfig(settings, init);
  console.log(init.data);
  // Get customer ID from init object
  const customerId = init?.data?.customer?.id;
  let clientId: string | null = null;

  // Helper function to handle customer linking detection
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

  // Helper function to enhance events with customer ID (no customer linking logic)
  const enhanceEventWithCustomerId = (event: any) => {
    return {
      ...event,
      ...(customerId && { customerId }),
    };
  };

  // Standard Shopify events
  analytics.subscribe(SUBSCRIBABLE_EVENTS.PAGE_VIEWED, async (event: any) => {
    // Handle customer linking detection (only on first event with clientId)
    handleCustomerLinking(event);

    const enhancedEvent = enhanceEventWithCustomerId(event);
    await sendEvent(enhancedEvent, config);
  });
  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_ADDED_TO_CART,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      handleCustomerLinking(event);

      const enhancedEvent = enhanceEventWithCustomerId(event);
      await sendEvent(enhancedEvent, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_REMOVED_FROM_CART,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      handleCustomerLinking(event);

      const enhancedEvent = enhanceEventWithCustomerId(event);
      await sendEvent(enhancedEvent, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_VIEWED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      handleCustomerLinking(event);

      const enhancedEvent = enhanceEventWithCustomerId(event);
      await sendEvent(enhancedEvent, config);
    },
  );

  analytics.subscribe(SUBSCRIBABLE_EVENTS.CART_VIEWED, async (event: any) => {
    // Handle customer linking detection (only on first event with clientId)
    handleCustomerLinking(event);

    const enhancedEvent = enhanceEventWithCustomerId(event);
    await sendEvent(enhancedEvent, config);
  });

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.COLLECTION_VIEWED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      handleCustomerLinking(event);

      const enhancedEvent = enhanceEventWithCustomerId(event);
      await sendEvent(enhancedEvent, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.SEARCH_SUBMITTED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      handleCustomerLinking(event);

      const enhancedEvent = enhanceEventWithCustomerId(event);
      await sendEvent(enhancedEvent, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.CHECKOUT_STARTED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      handleCustomerLinking(event);

      const enhancedEvent = enhanceEventWithCustomerId(event);
      await sendEvent(enhancedEvent, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.CHECKOUT_COMPLETED,
    async (event: any) => {
      // Handle customer linking detection (only on first event with clientId)
      handleCustomerLinking(event);

      const enhancedEvent = enhanceEventWithCustomerId(event);
      await sendEvent(enhancedEvent, config);
    },
  );
});
