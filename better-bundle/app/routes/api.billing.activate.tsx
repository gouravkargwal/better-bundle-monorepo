import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { invalidateSuspensionCache } from "../middleware/serviceSuspension";
import { logSuspensionEvent } from "../services/suspensionAudit.service";
import logger from "app/utils/logger";
import { incrementCounter } from "../services/metrics.service";

export async function action({ request }: ActionFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const { shop } = session;

  try {
    const formData = await request.formData();
    const subscriptionId = formData.get("subscription_id") as string;

    logger.info({ shop, subscriptionId }, "Billing activation started");

    if (!subscriptionId) {
      logger.warn({ shop }, "Billing activation failed: no subscription ID");
      incrementCounter("billing.activate.validation_error", {
        shop,
        reason: "missing_subscription_id",
      });
      return json(
        { success: false, error: "Subscription ID is required" },
        { status: 400 },
      );
    }

    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true },
    });

    if (!shopRecord) {
      logger.warn({ shop }, "Billing activation failed: shop not found");
      incrementCounter("billing.activate.error", {
        shop,
        reason: "shop_not_found",
      });
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    // Get shop subscription
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        is_active: true,
      },
    });

    if (!shopSubscription) {
      return json(
        { success: false, error: "Shop subscription not found" },
        { status: 404 },
      );
    }

    // --- Ownership verification ---

    // If the subscription already has a Shopify subscription ID assigned
    // and it differs from the incoming one, reject the request
    if (
      shopSubscription.shopify_subscription_id &&
      shopSubscription.shopify_subscription_id !== subscriptionId
    ) {
      logger.warn(
        {
          shop,
          existingSubscriptionId: shopSubscription.shopify_subscription_id,
          incomingSubscriptionId: subscriptionId,
        },
        "Subscription ownership mismatch: shop already has a different subscription",
      );
      return json(
        {
          success: false,
          error:
            "This shop already has an active subscription. Cannot activate a different subscription.",
        },
        { status: 403 },
      );
    }

    // Verify the subscription exists in Shopify and belongs to this shop
    // The admin GraphQL client is scoped to the current shop, so a successful
    // response confirms the subscription is owned by this shop
    try {
      const query = `
        query getSubscription($id: ID!) {
          node(id: $id) {
            ... on AppSubscription {
              id
              status
              test
            }
          }
        }
      `;

      const response = await admin.graphql(query, {
        variables: { id: subscriptionId },
      });
      const result: {
        data?: { node?: { id: string; status: string; test: boolean } | null };
      } = await response.json();

      if (!result?.data?.node) {
        logger.warn(
          { shop, subscriptionId },
          "Subscription not found in Shopify during activation",
        );
        return json(
          {
            success: false,
            error: "Subscription not found in Shopify. Please try again.",
          },
          { status: 404 },
        );
      }
    } catch (graphqlError) {
      logger.error(
        { error: graphqlError, shop, subscriptionId },
        "Failed to verify subscription in Shopify during activation",
      );
      return json(
        {
          success: false,
          error: "Could not verify subscription. Please try again later.",
        },
        { status: 502 },
      );
    }

    // Update shop subscription status
    // ✅ When subscription is activated, convert from TRIAL to PAID
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        shopify_subscription_id: subscriptionId,
        shopify_status: "ACTIVE",
        subscription_type: "PAID", // ✅ FIX: Change from TRIAL to PAID when subscription is active
        status: "ACTIVE",
        updated_at: new Date(),
      },
    });

    // Reactivate shop services
    await prisma.shops.updateMany({
      where: { shop_domain: shop },
      data: {
        is_active: true,
        suspended_at: null,
        suspension_reason: null,
        service_impact: null,
        updated_at: new Date(),
      },
    });

    // Log the reactivation event to the audit trail
    await logSuspensionEvent({
      shopId: shopRecord.id,
      action: "REACTIVATED",
      reason: `Subscription ${subscriptionId} activated`,
      triggeredBy: "system",
    });

    // Invalidate suspension cache for all shops with this domain
    const shopRecords = await prisma.shops.findMany({
      where: { shop_domain: shop },
      select: { id: true },
    });

    for (const shopRecord of shopRecords) {
      await invalidateSuspensionCache(shopRecord.id);
    }

    logger.info(
      { shop, subscriptionId, shopId: shopRecord.id },
      "Billing activation completed successfully",
    );
    incrementCounter("billing.activate.completed", { shop, subscriptionId });

    return json({
      success: true,
      message: "Subscription activated successfully",
      subscription_id: subscriptionId,
    });
  } catch (error) {
    logger.error({ error, shop }, "Error activating subscription");
    incrementCounter("billing.activate.error", { shop, reason: "exception" });
    return json(
      {
        success: false,
        error: "An internal error occurred. Please try again later.",
      },
      { status: 500 },
    );
  }
}
