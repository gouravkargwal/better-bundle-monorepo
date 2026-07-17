import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import logger from "app/utils/logger";

export async function action({ request }: ActionFunctionArgs) {
  const { shop, payload } = await authenticate.webhook(request);

  try {
    const billingAttempt = payload.subscription_billing_attempt;
    const subscriptionId = billingAttempt?.subscription_id;

    if (!subscriptionId) {
      logger.error({ shop }, "No billing attempt data in success webhook");
      return json(
        { success: false, error: "No billing data" },
        { status: 400 },
      );
    }

    // Flat monthly plan is billed and renewed natively by Shopify's recurring
    // AppSubscription — nothing to reconcile locally beyond logging receipt.
    logger.info(
      { shop, subscriptionId, amount: billingAttempt?.amount },
      "Billing success webhook received",
    );

    return json({ success: true });
  } catch (error) {
    logger.error({ error, shop }, "Error processing billing success");
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}
