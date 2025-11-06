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
    logger.error(
      { error: error instanceof Error ? error.message : String(error) },
      "Error processing GDPR customer data request",
    );
    // Still return 200 to prevent retries
    return new Response();
  }
};
