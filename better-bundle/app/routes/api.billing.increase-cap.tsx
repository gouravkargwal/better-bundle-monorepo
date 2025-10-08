import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

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
      id: billingPlan.subscription_line_item_id,
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

    // Update billing cycle cap
    await prisma.billing_cycles.update({
      where: { id: currentCycle.id },
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
