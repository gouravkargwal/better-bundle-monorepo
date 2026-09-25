import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import logger from "../utils/logger";
import { eraseCustomerData } from "../services/dataErasure.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { shop, topic, payload } = await authenticate.webhook(request);

    const customerId = payload?.customer?.id
      ? String(payload.customer.id)
      : null;
    const ordersToRedact: string[] = (payload?.orders_to_redact ?? []).map(
      (id: unknown) => String(id),
    );

    logger.info(
      { shop, topic, customerId, orderCount: ordersToRedact.length },
      "GDPR customer redact request received",
    );

    try {
      const { erased, shopFound } = await eraseCustomerData(
        shop,
        customerId,
        ordersToRedact,
      );
      logger.info(
        { shop, customerId, shopFound, erased },
        "GDPR customer redact completed",
      );
    } catch (erasureError) {
      // Acknowledge regardless: a non-200 makes Shopify retry the same request,
      // and a retry will not fix a broken query. The alert is the log line, and
      // it has to be loud, because silently failing to delete is the one
      // outcome with a legal edge to it.
      logger.error(
        {
          error:
            erasureError instanceof Error
              ? erasureError.message
              : String(erasureError),
          shop,
          customerId,
        },
        "🚨 GDPR customer redact FAILED - personal data may still be held",
      );
    }

    return new Response();
  } catch (error) {
    // According to Shopify docs: "If a mandatory compliance webhook sends a request 
    // with an invalid Shopify HMAC header, then the app must return a 401 Unauthorized HTTP status."
    logger.error(
      { error: error instanceof Error ? error.message : String(error) },
      "HMAC verification failed for GDPR customer redact request",
    );
    // Return 401 for invalid HMAC (required by Shopify for compliance webhooks)
    return new Response(null, { status: 401 });
  }
};
