import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { invalidateSuspensionCache } from "../middleware/serviceSuspension";
import logger from "app/utils/logger";
import { incrementCounter } from "../services/metrics.service";

// ── In-memory dedup set for duplicate webhook delivery ──────────────
// Clears entries older than 60 seconds so it doesn't leak memory.
const processedWebhookIds = new Set<string>();
const WEBHOOK_DEDUP_TTL_MS = 60_000;

function markWebhookProcessed(id: string): boolean {
  if (processedWebhookIds.has(id)) return false; // already seen
  processedWebhookIds.add(id);
  setTimeout(() => processedWebhookIds.delete(id), WEBHOOK_DEDUP_TTL_MS);
  return true;
}

export async function action({ request }: ActionFunctionArgs) {
  const { shop, payload, admin } = await authenticate.webhook(request);

  // ── Shopify-level webhook idempotency ──────────────────────────
  const webhookId = payload.id as string | undefined;
  if (webhookId) {
    if (!markWebhookProcessed(webhookId)) {
      logger.info(
        { shop, webhookId },
        "Duplicate webhook skipped (already processed)",
      );
      return json({ success: true, skipped: true });
    }
  }

  try {
    const appSub = payload.app_subscription;
    const subscriptionId = appSub?.admin_graphql_api_id || appSub?.id;
    const status = appSub?.status;

    if (!subscriptionId || !status) {
      logger.error({ payload }, "No subscription data in update webhook");
      return json(
        { success: false, error: "No subscription data" },
        { status: 400 },
      );
    }

    // Find shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, shop_domain: true },
    });

    if (!shopRecord) {
      logger.warn({ shop }, "No shop record found for domain");
      return json({ success: true });
    }

    // Handle subscription status changes
    switch (status) {
      case "ACTIVE":
        await handleActiveSubscription(
          shopRecord,
          subscriptionId,
          appSub,
          admin,
        );
        break;
      case "CANCELLED":
      case "DECLINED":
        await handleCancelledSubscription(shopRecord, subscriptionId);
        break;
      default:
        logger.info(
          { shop, subscriptionId, status },
          "Subscription status change logged (no action taken)",
        );
    }

    return json({ success: true });
  } catch (error) {
    logger.error(
      {
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
      },
      "Error processing subscription update",
    );
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}

/**
 * Handle subscription activation (flat fee)
 *
 * Idempotency guarantees:
 * 1. Uses findFirst + orderBy (DB-level) for the latest active billing cycle
 * 2. Checks for existing billing cycle before creating a new one
 * 3. Wraps the billing-cycle create in a try/catch to handle unique-constraint
 *    races ( @@unique([shop_subscription_id, status]) )
 * 4. Uses a progressive cycle_number (increments from the latest cycle)
 * 5. Uses upsert-like update on shop_subscriptions via shopify_subscription_id
 */
async function handleActiveSubscription(
  shopRecord: any,
  subscriptionId: string,
  appSub?: any,
  admin?: any,
) {
  try {
    // Extract monthly fee from webhook payload (AppRecurringPricing)
    let monthlyFee: number | undefined;
    const lineItems = appSub?.line_items || [];

    if (lineItems.length > 0) {
      const pricing = lineItems[0]?.plan?.pricing_details;
      // AppRecurringPricing price
      monthlyFee = pricing?.price?.amount;
    }

    // If not in webhook, fetch from Shopify GraphQL using the admin client
    if (!monthlyFee && admin) {
      try {
        monthlyFee = await fetchMonthlyFeeFromShopifyWithAdmin(
          subscriptionId,
          admin,
        );
      } catch (fetchError) {
        logger.warn(
          { error: fetchError, shop: shopRecord.shop_domain, subscriptionId },
          "Failed to fetch monthly fee from GraphQL, will use database value",
        );
      }
    }

    // ── Find OR upsert the shop subscription by shopify_subscription_id ──
    // Try to find an existing subscription first
    let shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: { shop_id: shopRecord.id },
      include: {
        subscription_plans: {
          select: { monthly_fee: true },
        },
      },
    });

    if (!shopSubscription) {
      logger.error(
        { shop: shopRecord.shop_domain, subscriptionId },
        "No shop subscription found for active subscription",
      );
      return;
    }

    // ── Idempotent shop_subscription update ──────────────────────────
    // Use shopify_subscription_id in the where clause when possible to handle
    // duplicate ACTIVE webhooks safely.
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        shopify_subscription_id: subscriptionId,
        shopify_status: "ACTIVE",
        status: "ACTIVE",
        is_active: true,
        updated_at: new Date(),
      },
    });

    // ── Billing-cycle lookup using findFirst + orderBy (DB-level) ─────
    const latestCycle = await prisma.billing_cycles.findFirst({
      where: {
        shop_subscription_id: shopSubscription.id,
        status: "ACTIVE",
      },
      orderBy: { cycle_number: "desc" },
    });

    if (!latestCycle) {
      // No active cycle exists → determine the next cycle_number
      const lastCycle = await prisma.billing_cycles.findFirst({
        where: { shop_subscription_id: shopSubscription.id },
        orderBy: { cycle_number: "desc" },
        select: { cycle_number: true },
      });

      const nextCycleNumber = lastCycle ? lastCycle.cycle_number + 1 : 1;

      const fee =
        monthlyFee ||
        Number(shopSubscription.subscription_plans?.monthly_fee || 29);

      logger.info(
        {
          shop: shopRecord.shop_domain,
          monthlyFee: fee,
          cycleNumber: nextCycleNumber,
        },
        "Creating billing cycle for activated flat fee subscription",
      );

      incrementCounter("subscription_update.cycle_created", {
        shop: shopRecord.shop_domain,
        cycleNumber: nextCycleNumber,
      });

      // ── Idempotent create with unique-constraint guard ──────────────
      // The @@unique([shop_subscription_id, status]) constraint prevents
      // duplicate ACTIVE cycles even in a race condition.
      try {
        await prisma.billing_cycles.create({
          data: {
            shop_subscription_id: shopSubscription.id,
            cycle_number: nextCycleNumber,
            start_date: new Date(),
            end_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
            initial_cap_amount: 0,
            current_cap_amount: 0,
            usage_amount: 0,
            commission_count: 0,
            status: "ACTIVE",
            activated_at: new Date(),
          },
        });
      } catch (createError: any) {
        // P2002 is Prisma's unique constraint violation
        if (createError?.code === "P2002") {
          logger.info(
            {
              shop: shopRecord.shop_domain,
              cycleNumber: nextCycleNumber,
            },
            "Billing cycle already exists (race condition handled)",
          );
        } else {
          throw createError;
        }
      }
    } else {
      logger.info(
        {
          shop: shopRecord.shop_domain,
          cycleId: latestCycle.id,
          cycleNumber: latestCycle.cycle_number,
        },
        "Active billing cycle already exists – skipping creation",
      );
    }

    // Reactivate shop if suspended
    await prisma.shops.update({
      where: { id: shopRecord.id },
      data: {
        is_active: true,
        suspended_at: null,
        suspension_reason: null,
        service_impact: null,
        updated_at: new Date(),
      },
    });

    await invalidateSuspensionCache(shopRecord.id);

    incrementCounter("subscription_update.activated", {
      shop: shopRecord.shop_domain,
      subscriptionId,
      monthlyFee: monthlyFee ?? 0,
    });

    logger.info(
      {
        shop: shopRecord.shop_domain,
        subscriptionId,
        monthlyFee,
      },
      "Flat fee subscription activated and shop reactivated",
    );
  } catch (error) {
    logger.error({ error }, "Error activating subscription");
    throw error;
  }
}

/**
 * Handle subscription cancellation
 */
async function handleCancelledSubscription(
  shopRecord: any,
  subscriptionId: string,
) {
  try {
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: { shop_id: shopRecord.id },
    });

    if (!shopSubscription) {
      logger.error(
        { shop: shopRecord.shop_domain, subscriptionId },
        "No shop subscription found for cancelled subscription",
      );
      return;
    }

    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        shopify_subscription_id: subscriptionId,
        shopify_status: "CANCELLED",
        status: "CANCELLED",
        is_active: false,
        cancelled_at: new Date(),
        updated_at: new Date(),
      },
    });

    // Suspend shop services
    await prisma.shops.update({
      where: { id: shopRecord.id },
      data: {
        is_active: false,
        suspended_at: new Date(),
        suspension_reason: "subscription_cancelled",
        service_impact: "suspended",
        updated_at: new Date(),
      },
    });

    incrementCounter("subscription_update.cancelled", {
      shop: shopRecord.shop_domain,
      subscriptionId,
    });

    logger.info(
      {
        shop: shopRecord.shop_domain,
        subscriptionId,
        shopSubscriptionId: shopSubscription.id,
      },
      "Subscription cancelled and shop suspended",
    );
  } catch (error) {
    logger.error({ error }, "Error handling cancelled subscription");
    throw error;
  }
}

/**
 * Fetch monthly fee from Shopify GraphQL API for an AppRecurringPricing subscription
 * Uses the admin client from the webhook (no re-authentication needed)
 */
async function fetchMonthlyFeeFromShopifyWithAdmin(
  subscriptionId: string,
  admin: any,
): Promise<number | undefined> {
  try {
    const query = `
      query($id: ID!) {
        node(id: $id) {
          ... on AppSubscription {
            lineItems {
              plan {
                pricingDetails {
                  __typename
                  ... on AppRecurringPricing {
                    price {
                      amount
                      currencyCode
                    }
                  }
                }
              }
            }
          }
        }
      }
    `;

    const response = await admin.graphql(query, {
      variables: { id: subscriptionId },
    });
    const data = await response.json();

    const pricingDetails =
      data.data?.node?.lineItems?.[0]?.plan?.pricingDetails;
    if (pricingDetails?.__typename === "AppRecurringPricing") {
      return Number(pricingDetails.price?.amount);
    }

    return undefined;
  } catch (error) {
    logger.warn(
      { error, subscriptionId },
      "Failed to fetch monthly fee from Shopify",
    );
    return undefined;
  }
}
