import { BACKEND_URL } from "../config/constants";
import { logger } from "../utils/logger";

/**
 * Record offer outcome for incrementality tracking.
 * Called when user adds a recommended product to cart or declines.
 */
export const recordOfferOutcome = async (
  impressionId,
  outcome,
  revenueAdded,
) => {
  try {
    const url = `${BACKEND_URL}/api/interaction/outcome`;
    const payload = {
      impression_id: impressionId,
      outcome,
    };
    if (revenueAdded !== undefined) {
      payload.revenue_added = revenueAdded;
    }
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    });
    return response.ok;
  } catch (error) {
    logger.error({ error }, "Mercury: Failed to record offer outcome");
    return false;
  }
};
