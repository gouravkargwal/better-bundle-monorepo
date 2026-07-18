import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { invalidateSuspensionCache } from "../middleware/serviceSuspension";
import logger from "app/utils/logger";

export async function action({ request }: ActionFunctionArgs) {
  const { shop, payload, admin } = await authenticate.webhook(request);

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
        await handleActiveSubscription(shopRecord, subscriptionId, appSub, admin);
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
      // Try AppRecurringPricing price first, then AppUsagePricing capped amount
      monthlyFee =
        pricing?.price?.amount ||
        pricing?.capped_amount?.amount ||
        pricing?.cappedAmount?.amount;
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

    // Find the shop subscription record
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: { shop_id: shopRecord.id },
      include: {
        pricing_tiers: true,
        billing_cycles: true,
      },
    });

    if (!shopSubscription) {
      logger.error(
        { shop: shopRecord.shop_domain, subscriptionId },
        "No shop subscription found for active subscription",
      );
      return;
    }

    // Update shop subscription to PAID status
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        shopify_subscription_id: subscriptionId,
        shopify_status: "ACTIVE",
        subscription_type: "PAID",
        status: "ACTIVE",
        is_active: true,
        updated_at: new Date(),
      },
    });

    // Create billing cycle if it doesn't exist
    const activeCycle = shopSubscription.billing_cycles?.find(
      (cycle: any) => cycle.status === "ACTIVE",
    );

    if (!activeCycle) {
      const fee =
        monthlyFee ||
        Number(
          shopSubscription.monthly_fee_override ||
            shopSubscription.pricing_tiers?.monthly_fee ||
            29,
        );

      logger.info(
        {
          shop: shopRecord.shop_domain,
          monthlyFee: fee,
        },
        "Creating billing cycle for activated flat fee subscription",
      );

      await prisma.billing_cycles.create({
        data: {
          shop_subscription_id: shopSubscription.id,
          cycle_number: 1,
          start_date: new Date(),
          end_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
          period_fee: fee,
          status: "ACTIVE",
          activated_at: new Date(),
        },
      });
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
