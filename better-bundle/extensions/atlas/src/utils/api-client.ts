import type { AtlasConfig } from "../types";

export const sendEvent = async (event: any, config: AtlasConfig) => {
  const url = `${config.backendUrl}/collect/behavioral-events`;
  try {
    const payload = {
      ...event,
      shop_domain: config.shopDomain,
    };
    console.log(payload);
    const jsonData = JSON.stringify(payload);
    navigator.sendBeacon(url, jsonData);
  } catch (error) {
    console.log("💥 Request error:", error);
    throw error;
  }
};
