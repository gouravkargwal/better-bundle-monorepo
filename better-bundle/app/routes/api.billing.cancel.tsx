// app/routes/api.billing.cancel.tsx

import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import logger from "../utils/logger";
import { incrementCounter } from "../services/metrics.service";

export async function action({ request }: ActionFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const { shop } = session;

  try {
    logger.info({ shop }, "Billing cancellation started");

    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true },
    });

    if (!shopRecord) {
      logger.warn({ shop }, "Billing cancellation failed: shop not found");
      incrementCounter("billing.cancel.error", {
        shop,
        reason: "shop_not_found",
      });
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        // Include both active and suspended subscriptions (pending approval)
        OR: [{ is_active: true }, { status: "SUSPENDED" }],
      },
      orderBy: {
        created_at: "desc",
      },
    });

    if (!shopSubscription) {
      logger.warn(
        { shop },
        "Billing cancellation failed: no active subscription",
      );
      incrementCounter("billing.cancel.validation_error", {
        shop,
        reason: "no_active_subscription",
      });
      return json({
        success: false,
        error: "No active subscription found",
      });
    }

    // ✅ Cancel in Shopify if subscription exists and is not already cancelled
    if (
      shopSubscription.shopify_subscription_id &&
      shopSubscription.shopify_status !== "CANCELLED"
    ) {
      try {
        const mutation = `
          mutation appSubscriptionCancel($id: ID!) {
            appSubscriptionCancel(id: $id) {
              userErrors {
                field
                message
              }
              appSubscription {
                id
                status
              }
            }
          }
        `;

        const variables = {
          id: shopSubscription.shopify_subscription_id,
        };

        const response = await admin.graphql(mutation, { variables });
        const result = await response.json();

        logger.info(
          {
            shop,
            subscriptionId: shopSubscription.shopify_subscription_id,
            result: result.data,
          },
          "Subscription cancellation response",
        );

        if (result.data?.appSubscriptionCancel?.userErrors?.length > 0) {
          const errors = result.data.appSubscriptionCancel.userErrors;
          logger.warn(
            {
              errors,
              subscriptionId: shopSubscription.shopify_subscription_id,
            },
            "Errors cancelling in Shopify (continuing anyway)",
          );
        }
      } catch (error) {
        logger.error(
          {
            error,
            subscriptionId: shopSubscription.shopify_subscription_id,
          },
          "Error cancelling subscription in Shopify (continuing with local cancellation)",
        );
      }
    } else if (shopSubscription.shopify_status === "CANCELLED") {
      logger.info({ shop }, "Subscription already cancelled in Shopify");
    } else {
      logger.info({ shop }, "No Shopify subscription to cancel");
    }

    // ✅ Update subscription status since they're starting over
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        shopify_status: "CANCELLED",
        status: "TRIAL_COMPLETED", // Reset to trial completed so they can set up again
        is_active: true, // Reactivate so they can set up billing again
        cancelled_at: new Date(),
        updated_at: new Date(),
      },
    });

    logger.info({ shop }, "Subscription cancelled successfully");
    incrementCounter("billing.cancel.completed", { shop });

    return json({
      success: true,
      message: "Subscription cancelled. You can set up a new subscription.",
    });
  } catch (error) {
    logger.error({ error, shop }, "Error cancelling subscription");
    incrementCounter("billing.cancel.error", { shop, reason: "exception" });
    return json(
      {
        success: false,
        error: "An internal error occurred. Please try again later.",
      },
      { status: 500 },
    );
  }
}
