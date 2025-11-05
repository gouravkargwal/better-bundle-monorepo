import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { invalidateSuspensionCache } from "../middleware/serviceSuspension";
import logger from "app/utils/logger";

export async function action({ request }: ActionFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Parse request body to get new spending limit
    const body = await request.json();
    const newSpendingLimit = body.spendingLimit || 1000.0;

    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: {
        id: true,
        currency_code: true,
        suspension_reason: true,
      },
    });

    if (!shopRecord) {
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    // Get current shop subscription and billing cycle
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        is_active: true,
        status: "ACTIVE",
      },
      include: {
        billing_cycles: {
          where: { status: "ACTIVE" },
          orderBy: { cycle_number: "desc" },
          take: 1,
        },
      },
    });

    if (!shopSubscription) {
      return json(
        { success: false, error: "No active subscription found" },
        { status: 404 },
      );
    }

    const currentCycle = shopSubscription.billing_cycles[0];
    if (!currentCycle) {
      return json(
        { success: false, error: "No active billing cycle found" },
        { status: 404 },
      );
    }

    // Check if new limit is higher than current
    const currentCap = Number(currentCycle.current_cap_amount);
    if (newSpendingLimit <= currentCap) {
      return json(
        { success: false, error: "New cap must be higher than current cap" },
        { status: 400 },
      );
    }

    // Update Shopify subscription with new capped amount
    const currency = shopRecord.currency_code || "USD";
    const shopifyLineItemId = shopSubscription.shopify_line_item_id;

    if (!shopifyLineItemId) {
      return json(
        { success: false, error: "No Shopify line item ID found" },
        { status: 404 },
      );
    }

    // Use Shopify GraphQL to update subscription
    // Note: AppSubscriptionLineItemUpdatePayload returns appSubscription, not appSubscriptionLineItem
    const mutation = `
      mutation appSubscriptionLineItemUpdate($id: ID!, $cappedAmount: MoneyInput!) {
        appSubscriptionLineItemUpdate(
          id: $id
          cappedAmount: $cappedAmount
        ) {
          userErrors {
            field
            message
          }
          confirmationUrl
          appSubscription {
            id
            status
            lineItems {
              id
              plan {
                pricingDetails {
                  __typename
                  ... on AppUsagePricing {
                    terms
                    cappedAmount {
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

    const variables = {
      id: shopifyLineItemId,
      cappedAmount: {
        amount: newSpendingLimit.toString(),
        currencyCode: currency,
      },
    };

    const response = await admin.graphql(mutation, { variables });
    const data = await response.json();

    // Check for user errors first
    if (data.data?.appSubscriptionLineItemUpdate?.userErrors?.length > 0) {
      logger.error(
        {
          errors: data.data.appSubscriptionLineItemUpdate.userErrors,
          shopifyLineItemId,
        },
        "Shopify GraphQL errors while updating subscription",
      );
      const errorMessage =
        data.data.appSubscriptionLineItemUpdate.userErrors[0]?.message ||
        "Failed to update subscription in Shopify";
      return json({ success: false, error: errorMessage }, { status: 500 });
    }

    // Check if merchant approval is required (confirmationUrl is returned)
    const confirmationUrl =
      data.data?.appSubscriptionLineItemUpdate?.confirmationUrl;
    if (confirmationUrl) {
      logger.info(
        { shopifyLineItemId, confirmationUrl },
        "Cap increase requires merchant approval",
      );
      // Return the confirmation URL so the frontend can redirect
      return json({
        success: true,
        requiresApproval: true,
        confirmationUrl,
        message:
          "Please approve the cap increase in Shopify to complete the update",
      });
    }

    // Update billing plan with new cap
    // Note: billing_cycle_adjustments table may not exist in all schemas
    // This is optional tracking - main cap update happens below

    // ✅ ATOMIC: Update billing cycle cap with race condition protection
    await prisma.billing_cycles.update({
      where: {
        id: currentCycle.id,
        current_cap_amount: currentCap, // Only update if cap hasn't changed
      },
      data: {
        current_cap_amount: newSpendingLimit,
      },
    });

    // Reactivate shop subscription if it was suspended due to cap
    // Kafka consumer will handle reprocessing rejected commissions
    if (shopSubscription.status === "SUSPENDED") {
      await prisma.shop_subscriptions.update({
        where: { id: shopSubscription.id },
        data: {
          status: "ACTIVE",
          updated_at: new Date(),
        },
      });

      // Invalidate suspension cache so fresh data is fetched
      await invalidateSuspensionCache(shopRecord.id);

      logger.info(
        { shop_id: shopRecord.id, subscription_id: shopSubscription.id },
        "Reactivated shop subscription after cap increase",
      );
    }

    // ✅ Publish Kafka event to reprocess rejected commissions asynchronously
    try {
      const { KafkaProducerService } = await import(
        "../services/kafka/kafka-producer.service"
      );
      const kafkaProducer = await KafkaProducerService.getInstance();

      await kafkaProducer.publishShopifyUsageEvent({
        event_type: "cap_increase",
        shop_id: shopRecord.id,
        shop_domain: shop,
        billing_cycle_id: currentCycle.id,
        new_cap_amount: newSpendingLimit,
        old_cap_amount: currentCap,
      });

      logger.info(
        { shop_id: shopRecord.id, cycle_id: currentCycle.id },
        "Published cap increase event for reprocessing rejected commissions",
      );
    } catch (kafkaError) {
      logger.error(
        { error: kafkaError, shop_id: shopRecord.id },
        "Failed to publish cap increase event - reprocessing will happen when consumer processes next message",
      );
      // Don't fail the request - Kafka consumer will handle it eventually
    }

    return json({
      success: true,
      message: "Cap increased successfully",
      newCap: newSpendingLimit,
      previousCap: currentCap,
    });
  } catch (error) {
    logger.error({ error }, "Error increasing cap");
    return json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
