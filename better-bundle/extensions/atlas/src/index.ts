import { register } from "@shopify/web-pixels-extension";
import type { AtlasConfig } from "./types";
import { SUBSCRIBABLE_EVENTS } from "./config/constants";
import { sendEvent } from "./utils/api-client";

const createConfig = (settings: any, init: any): AtlasConfig => {
  let shopDomain = init?.data?.shop?.myshopifyDomain;
  return {
    backendUrl: settings.backend_url,
    shopDomain: shopDomain,
  };
};

register(({ analytics, settings, init }) => {
  const config = createConfig(settings, init);

  // Standard Shopify events
  analytics.subscribe(SUBSCRIBABLE_EVENTS.PAGE_VIEWED, async (event: any) => {
    await sendEvent(event, config);
  });
  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_ADDED_TO_CART,
    async (event: any) => {
      sendEvent(event, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_REMOVED_FROM_CART,
    async (event: any) => {
      sendEvent(event, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.PRODUCT_VIEWED,
    async (event: any) => {
      await sendEvent(event, config);
    },
  );

  analytics.subscribe(SUBSCRIBABLE_EVENTS.CART_VIEWED, async (event: any) => {
    sendEvent(event, config);
  });

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.COLLECTION_VIEWED,
    async (event: any) => {
      sendEvent(event, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.SEARCH_SUBMITTED,
    async (event: any) => {
      sendEvent(event, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.CHECKOUT_STARTED,
    async (event: any) => {
      sendEvent(event, config);
    },
  );

  analytics.subscribe(
    SUBSCRIBABLE_EVENTS.CHECKOUT_COMPLETED,
    async (event: any) => {
      sendEvent(event, config);
    },
  );

  // Custom widget interaction events
  window.addEventListener("betterbundle:widget:interaction", (event) => {
    // Send widget interaction to Python worker
    const customEvent = event as CustomEvent;
    sendEvent(
      {
        ...customEvent.detail,
        eventType: "widget_interaction",
        shop_domain: config.shopDomain,
      },
      config,
    );
  });

  // Attribution events for revenue tracking
  window.addEventListener("betterbundle:attribution:created", (event) => {
    // Send attribution to Python worker for revenue tracking
    const customEvent = event as CustomEvent;
    sendEvent(
      {
        ...customEvent.detail,
        eventType: "attribution_created",
        shop_domain: config.shopDomain,
      },
      config,
    );
  });
});
