import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import logger from "../utils/logger";
import { eraseShopData } from "../services/dataErasure.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { shop, topic } = await authenticate.webhook(request);

    logger.info({ shop, topic }, "GDPR shop redact request received");

    try {
      const { erased, shopFound } = await eraseShopData(shop);
      logger.info({ shop, shopFound, erased }, "GDPR shop redact completed");
    } catch (erasureError) {
      // Acknowledged regardless — see the note in customers_redact. A retry
      // cannot fix a broken query, so the log line is the alarm.
      logger.error(
        {
          error:
            erasureError instanceof Error
              ? erasureError.message
              : String(erasureError),
          shop,
        },
        "🚨 GDPR shop redact FAILED - shop data may still be held",
      );
    }

    return new Response();
  } catch (error) {
    // According to Shopify docs: "If a mandatory compliance webhook sends a request 
    // with an invalid Shopify HMAC header, then the app must return a 401 Unauthorized HTTP status."
    logger.error(
      { error: error instanceof Error ? error.message : String(error) },
      "HMAC verification failed for GDPR shop redact request",
    );
    // Return 401 for invalid HMAC (required by Shopify for compliance webhooks)
    return new Response(null, { status: 401 });
  }
};
