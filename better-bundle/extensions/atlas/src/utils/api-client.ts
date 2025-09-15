import type { AtlasConfig } from "../types";

export const sendEvent = async (event: any, config: AtlasConfig) => {
  const url = `https://d242bda5e5c7.ngrok-free.app/collect/behavioral-events`;

  try {
    const payload = {
      ...event,
      shop_domain: config.shopDomain,
    };

    await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      keepalive: true,
    });
  } catch (error) {
    console.log("💥 Request error:", error);
    throw error;
  }
};
