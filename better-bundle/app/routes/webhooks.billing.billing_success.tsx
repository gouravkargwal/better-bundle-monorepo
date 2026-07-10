import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
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

    logger.info(
      { shop, subscriptionId, amount: billingAttempt?.amount },
      "Billing success webhook received",
    );

    // Find shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true },
    });

    if (!shopRecord) {
      logger.warn({ shop }, "No shop record found for domain");
      return json({ success: true });
    }

    // Find shop subscription
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        is_active: true,
      },
      select: { id: true, user_chosen_cap_amount: true },
    });

    if (!shopSubscription) {
      logger.warn({ shop }, "No active subscription found for shop");
      return json({ success: true });
    }

    // Roll billing cycle: close current ACTIVE cycle and open the next one.
    // Idempotent — if no ACTIVE cycle exists, rollover was already processed
    // on a previous delivery of this webhook.
    const currentCycle = await prisma.billing_cycles.findFirst({
      where: { shop_subscription_id: shopSubscription.id, status: "ACTIVE" },
      select: { id: true, cycle_number: true },
    });

    if (currentCycle) {
      await prisma.billing_cycles.update({
        where: { id: currentCycle.id },
        data: { status: "COMPLETED", updated_at: new Date() },
      });

      const capAmount = shopSubscription.user_chosen_cap_amount || 1000;
      await prisma.billing_cycles.create({
        data: {
          shop_subscription_id: shopSubscription.id,
          cycle_number: currentCycle.cycle_number + 1,
          start_date: new Date(),
          end_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
          initial_cap_amount: capAmount,
          current_cap_amount: capAmount,
          usage_amount: 0,
          commission_count: 0,
          status: "ACTIVE",
          activated_at: new Date(),
        },
      });

      logger.info(
        { shop, cycleNumber: currentCycle.cycle_number + 1 },
        "Billing cycle rolled over",
      );
    } else {
      logger.info(
        { shop },
        "No active billing cycle — rollover already processed for this webhook",
      );
    }

    return json({ success: true });
  } catch (error) {
    logger.error({ error, shop }, "Error processing billing success");
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}
