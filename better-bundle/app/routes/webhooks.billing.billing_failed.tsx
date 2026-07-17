import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import logger from "../utils/logger";

export async function action({ request }: ActionFunctionArgs) {
  const { shop, payload } = await authenticate.webhook(request);

  try {
    const billingAttempt = payload.subscription_billing_attempt;
    const subscriptionId = billingAttempt?.subscription_id;
    const failureReason = billingAttempt?.failure_reason;

    if (!subscriptionId) {
      logger.error({ shop }, "No billing attempt data in failed webhook");
      return json(
        { success: false, error: "No billing data" },
        { status: 400 },
      );
    }

    // Flat monthly plan is billed by Shopify's recurring AppSubscription —
    // a failed charge means Shopify will retry/suspend per its own dunning
    // flow. We just log for visibility; the subscription's actual status is
    // synced via the APP_SUBSCRIPTIONS_UPDATE webhook.
    logger.warn(
      { shop, subscriptionId, failureReason },
      "Billing failure webhook received",
    );

    return json({ success: true });
  } catch (error) {
    logger.error({ error, shop }, "Error processing billing failure");
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}
