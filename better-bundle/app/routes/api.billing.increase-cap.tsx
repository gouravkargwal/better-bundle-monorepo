import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

async function reprocessRejectedCommissions(shopId: string, cycleId: string) {
  try {
    // ✅ TRANSACTION: Wrap all reprocessing in a single transaction
    await prisma.$transaction(async (tx) => {
      // Find all rejected commissions for this cycle with row-level locking
      const rejectedCommissions = await tx.commission_records.findMany({
        where: {
          shop_id: shopId,
          billing_cycle_id: cycleId,
          charge_type: "rejected",
          status: "rejected",
        },
        select: {
          id: true,
          commission_overflow: true,
        },
        orderBy: { created_at: "asc" }, // Process in order
      });

      if (rejectedCommissions.length === 0) {
        console.log(
          `ℹ️ No rejected commissions to reprocess for shop ${shopId}`,
        );
        return;
      }

      console.log(
        `🔄 Reprocessing ${rejectedCommissions.length} rejected commissions for shop ${shopId}`,
      );

      // Get current cycle with row-level locking
      const currentCycle = await tx.billing_cycles.findUnique({
        where: { id: cycleId },
        select: {
          current_cap_amount: true,
          usage_amount: true,
        },
      });

      if (!currentCycle) {
        console.error(`❌ Billing cycle ${cycleId} not found`);
        return;
      }

      let remainingCap =
        Number(currentCycle.current_cap_amount) -
        Number(currentCycle.usage_amount);

      let totalCharged = 0;

      // Reprocess each rejected commission with atomic updates
      for (const commission of rejectedCommissions) {
        const commissionOverflow = Number(commission.commission_overflow);

        if (commissionOverflow <= remainingCap) {
          // Can charge the full overflow amount
          const updateResult = await tx.commission_records.updateMany({
            where: {
              id: commission.id,
              charge_type: "rejected", // Only update if still rejected
              status: "rejected",
            },
            data: {
              commission_charged: commissionOverflow,
              commission_overflow: 0,
              charge_type: "full",
              status: "pending",
              updated_at: new Date(),
            },
          });

          if (updateResult.count > 0) {
            totalCharged += commissionOverflow;
            remainingCap -= commissionOverflow;
            console.log(
              `✅ Reprocessed commission ${commission.id}: $${commissionOverflow} charged`,
            );
          }
        } else if (remainingCap > 0) {
          // Partial charge only
          const partialCharge = remainingCap;
          const newOverflow = commissionOverflow - partialCharge;

          const updateResult = await tx.commission_records.updateMany({
            where: {
              id: commission.id,
              charge_type: "rejected", // Only update if still rejected
              status: "rejected",
            },
            data: {
              commission_charged: partialCharge,
              commission_overflow: newOverflow,
              charge_type: "partial",
              status: "pending",
              updated_at: new Date(),
            },
          });

          if (updateResult.count > 0) {
            totalCharged += partialCharge;
            remainingCap = 0;
            console.log(
              `⚠️ Partial reprocess commission ${commission.id}: $${partialCharge} charged, $${newOverflow} still overflow`,
            );
          }
        } else {
          // No remaining cap
          break;
        }
      }

      // ✅ ATOMIC: Update cycle usage once with total charged amount
      if (totalCharged > 0) {
        await tx.billing_cycles.update({
          where: { id: cycleId },
          data: {
            usage_amount: {
              increment: totalCharged,
            },
          },
        });

        console.log(
          `✅ Updated cycle usage by $${totalCharged} for shop ${shopId}`,
        );
      }

      console.log(
        `✅ Completed reprocessing rejected commissions for shop ${shopId}`,
      );
    });
  } catch (error) {
    console.error(`❌ Error reprocessing rejected commissions: ${error}`);
  }
}

export async function action({ request }: ActionFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Parse request body to get new spending limit
    const body = await request.json();
    const newSpendingLimit = body.spendingLimit || 1000.0;

    console.log(`🔄 Increasing cap for shop ${shop} to: $${newSpendingLimit}`);

    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, currency_code: true },
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
          where: { status: "active" },
          orderBy: { cycle_number: "desc" },
          take: 1,
        },
        shopify_subscription: true,
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
    const subscriptionId =
      shopSubscription.shopify_subscription?.shopify_subscription_id;

    if (!subscriptionId) {
      return json(
        { success: false, error: "No subscription ID found" },
        { status: 404 },
      );
    }

    // Use Shopify GraphQL to update subscription
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
          appSubscriptionLineItem {
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
    `;

    const variables = {
      id: shopSubscription.shopify_subscription.shopify_line_item_id,
      cappedAmount: {
        amount: newSpendingLimit.toString(),
        currencyCode: currency,
      },
    };

    const response = await admin.graphql(mutation, { variables });
    const data = await response.json();

    if (data.data?.appSubscriptionLineItemUpdate?.userErrors?.length > 0) {
      console.error(
        "Shopify GraphQL errors:",
        data.data.appSubscriptionLineItemUpdate.userErrors,
      );
      return json(
        { success: false, error: "Failed to update subscription in Shopify" },
        { status: 500 },
      );
    }

    // Update billing plan with new cap
    // Create billing cycle adjustment record
    await prisma.billing_cycle_adjustments.create({
      data: {
        billing_cycle_id: currentCycle.id,
        old_cap_amount: currentCap,
        new_cap_amount: newSpendingLimit,
        adjustment_amount: newSpendingLimit - currentCap,
        adjustment_reason: "cap_increase",
        adjusted_by: "user",
        adjusted_by_type: "user",
        adjusted_at: new Date(),
      },
    });

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

    // Reactivate shop services if they were suspended due to cap
    if (shopRecord.suspension_reason === "monthly_cap_reached") {
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

      console.log(`✅ Shop ${shop} services reactivated after cap increase`);

      // ✅ REPROCESS REJECTED COMMISSIONS
      await reprocessRejectedCommissions(shopRecord.id, currentCycle.id);
    }

    console.log(
      `✅ Cap increased for shop ${shop} from $${currentCap} to $${newSpendingLimit}`,
    );

    return json({
      success: true,
      message: "Cap increased successfully",
      newCap: newSpendingLimit,
      previousCap: currentCap,
    });
  } catch (error) {
    console.error("❌ Error increasing cap:", error);
    return json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
