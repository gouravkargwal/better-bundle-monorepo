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

    // ✅ Get shop subscription - only allow if trial is completed
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        is_active: true,
        // ✅ Only allow if trial is completed
        status: "TRIAL_COMPLETED" as any,
      },
    });

    // Check if there's already a subscription that's not in TRIAL_COMPLETED status
    const otherActiveSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        is_active: true,
        status: {
          not: "TRIAL_COMPLETED" as any,
        },
      },
    });

    if (otherActiveSubscription) {
      return json({
        success: false,
        error: "Active subscription already exists",
        existingSubscription: otherActiveSubscription,
      });
    }

    if (!shopSubscription) {
      return json(
        {
          success: false,
          error: "No completed trial found. Please complete your trial first.",
        },
        { status: 400 },
      );
    }

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
      mutation appSubscriptionCreate($name: String!, $returnUrl: URL!, $lineItems: [AppSubscriptionLineItemInput!]!) {
        appSubscriptionCreate(
          name: $name
          returnUrl: $returnUrl
          lineItems: $lineItems
          test: ${process.env.NODE_ENV === "development" ? "true" : "false"}
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

    // Build return URL for GraphQL App Subscriptions
    // For GraphQL, use the app URL with proper shop parameter
    const returnUrl = `${process.env.SHOPIFY_APP_URL}/app/billing?shop=${shop}`;

    const variables = {
      name: "Better Bundle - Usage Based",
      // Redirect back to app after approval
      returnUrl: returnUrl,
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

    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        status: "PENDING_APPROVAL" as any, // ✅ NOW we set PENDING_APPROVAL
        user_chosen_cap_amount: monthlyCap, // Store user's chosen cap
        updated_at: new Date(),
      },
    });

    // Create Shopify subscription record
    await prisma.shopify_subscriptions.create({
      data: {
        shop_subscription_id: shopSubscription.id,
        shopify_subscription_id: subscription.id,
        shopify_line_item_id: subscription.lineItems[0].id,
        confirmation_url: confirmationUrl,
        status: "PENDING" as any,
        created_at: new Date(),
        error_count: "0", // Required field
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
