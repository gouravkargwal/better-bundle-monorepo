import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import logger from "../utils/logger";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { shop, topic, payload } = await authenticate.webhook(request);

    // Log/store request for compliance
    logger.info({ shop, topic }, "GDPR shop redact request received");

    // Handle shop data deletion/redaction
    // Return 200 to acknowledge receipt
    return new Response();
  } catch (error) {
    logger.error(
      { error: error instanceof Error ? error.message : String(error) },
      "Error processing GDPR shop redact request",
    );
    // Still return 200 to prevent retries
    return new Response();
  }
};
