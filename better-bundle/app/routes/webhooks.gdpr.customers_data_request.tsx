import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import logger from "../utils/logger";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { shop, topic, payload } = await authenticate.webhook(request);

    // Log/store request minimally for compliance handling
    logger.info(
      { shop, topic, customerId: payload?.customer?.id },
      "GDPR customer data request received",
    );

    // Handle data request - export customer data if needed
    // Return 200 to acknowledge receipt
    return new Response();
  } catch (error) {
    // According to Shopify docs: "If a mandatory compliance webhook sends a request
    // with an invalid Shopify HMAC header, then the app must return a 401 Unauthorized HTTP status."
    logger.error(
      { error: error instanceof Error ? error.message : String(error) },
      "HMAC verification failed for GDPR customer data request",
    );
    // Return 401 for invalid HMAC (required by Shopify for compliance webhooks)
    return new Response(null, { status: 401 });
  }
};
