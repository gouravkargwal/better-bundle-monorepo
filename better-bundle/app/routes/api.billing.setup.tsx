import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import logger from "app/utils/logger";

export async function action({ request }: ActionFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Parse request body to get monthly cap
    const body = await request.json();
    const monthlyCap = body.monthlyCap;

    // Validate monthly cap
    if (!monthlyCap || monthlyCap <= 0) {
      return json(
        {
          success: false,
          error: "Monthly cap is required and must be greater than 0",
        },
        { status: 400 },
      );
    }

    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, currency_code: true },
    });

    if (!shopRecord) {
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    // ✅ Get shop subscription - allow if trial is completed OR pending approval
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: { shop_id: shopRecord.id },
      include: {
        pricing_tiers: true,
      },
    });

    if (!shopSubscription) {
      return json(
        {
          success: false,
          error: "No subscription found",
        },
        { status: 400 },
      );
    }

    // ✅ Additional validation: Check if trial threshold was actually reached
    if (shopSubscription.status === "PENDING_APPROVAL") {
      const actualRevenue = await prisma.commission_records.aggregate({
        where: {
          shop_id: shopRecord.id,
          billing_phase: "TRIAL",
          status: {
            in: ["TRIAL_PENDING", "TRIAL_COMPLETED"],
          },
        },
        _sum: {
          attributed_revenue: true,
        },
      });

      const actualAccumulatedRevenue = Number(
        actualRevenue._sum?.attributed_revenue || 0,
      );
      const thresholdAmount = Number(
        shopSubscription.trial_threshold_override ||
          shopSubscription.pricing_tiers?.trial_threshold_amount ||
          0,
      );

      if (actualAccumulatedRevenue < thresholdAmount) {
        return json(
          {
            success: false,
            error:
              "Trial threshold not reached. Please complete your trial first.",
          },
          { status: 400 },
        );
      }
    }

    // ✅ No need to check existing Shopify subscriptions - we fetch status from Shopify API in real-time

    // Get default subscription plan and pricing tier
    const defaultPlan = await prisma.subscription_plans.findFirst({
      where: {
        is_active: true,
        is_default: true,
      },
    });

    if (!defaultPlan) {
      return json(
        { success: false, error: "No default subscription plan found" },
        { status: 500 },
      );
    }

    const defaultPricingTier = await prisma.pricing_tiers.findFirst({
      where: {
        subscription_plan_id: defaultPlan.id,
        currency: shopRecord.currency_code || "USD",
        is_active: true,
        is_default: true,
      },
    });

    if (!defaultPricingTier) {
      return json(
        { success: false, error: "No pricing tier found for currency" },
        { status: 500 },
      );
    }

    // Create Shopify subscription using GraphQL
    const currency = shopRecord.currency_code;
    const cappedAmount = monthlyCap; // User-selected monthly cap

    const mutation = `
      mutation appSubscriptionCreate($name: String!, $returnUrl: URL!, $lineItems: [AppSubscriptionLineItemInput!]!, $test: Boolean!) {
        appSubscriptionCreate(
          name: $name
          returnUrl: $returnUrl
          lineItems: $lineItems
          test: $test
        ) {
          userErrors {
            field
            message
          }
          confirmationUrl
          appSubscription {
            id
            name
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

    // For embedded apps, use the Shopify admin URL format
    // This ensures proper authentication and embedded app context
    const appHandle = process.env.SHOPIFY_APP_HANDLE || "better-bundle-dev";
    const returnUrl = `https://admin.shopify.com/store/${shop}/apps/${appHandle}/app/billing`;

    const variables = {
      name: "Better Bundle - Usage Based",
      // Redirect back to app after approval
      returnUrl: returnUrl,
      test: process.env.NODE_ENV === "development",
      lineItems: [
        {
          plan: {
            appUsagePricingDetails: {
              terms: `3% of attributed revenue (capped at $${cappedAmount}/month)`,
              cappedAmount: {
                amount: cappedAmount,
                currencyCode: currency,
              },
            },
          },
        },
      ],
    };

    const response = await admin.graphql(mutation, { variables });
    const result = await response.json();

    if (result.data?.appSubscriptionCreate?.userErrors?.length > 0) {
      const errors = result.data.appSubscriptionCreate.userErrors;
      logger.error({ errors }, "Shopify errors while creating subscription");
      return json(
        {
          success: false,
          error: errors.map((e: any) => e.message).join(", "),
        },
        { status: 400 },
      );
    }

    const subscription = result.data?.appSubscriptionCreate?.appSubscription;
    const confirmationUrl = result.data?.appSubscriptionCreate?.confirmationUrl;

    if (!subscription) {
      return json(
        { success: false, error: "Failed to create subscription" },
        { status: 500 },
      );
    }

    // ✅ Mark subscription as SUSPENDED - Backend role ends here, Shopify takes over
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        status: "SUSPENDED" as any, // Backend no longer tracks status
        user_chosen_cap_amount: monthlyCap, // Store user's chosen cap
        is_active: false,
        updated_at: new Date(),
      },
    });

    // Update shop subscription with Shopify subscription info
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        shopify_subscription_id: subscription.id,
        shopify_line_item_id: subscription.lineItems[0].id,
        confirmation_url: confirmationUrl,
        shopify_status: "PENDING",
        updated_at: new Date(),
      },
    });

    return json({
      success: true,
      subscription_id: subscription.id,
      confirmationUrl: confirmationUrl, // Use camelCase to match frontend expectation
      message: "Please approve the subscription in Shopify",
    });
  } catch (error) {
    logger.error({ error }, "Error in billing setup");
    return json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
