import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import logger from "app/utils/logger";
import { incrementCounter } from "../services/metrics.service";

export async function action({ request }: ActionFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const { shop } = session;

  // Declared here so catch block can reference them
  let planName: string | undefined;
  let monthlyFee: number | undefined;
  let trialDays: number | undefined;

  try {
    // Parse request body — expects planName and monthlyFee
    const body = await request.json();
    planName = body.planName;
    monthlyFee = body.monthlyFee;
    trialDays = body.trialDays;

    // Validate inputs
    const fee = Number(monthlyFee) || 29;
    const trial = Number(trialDays) || 14;

    logger.info({ shop, planName, fee, trial }, "Billing setup started");

    if (!planName) {
      logger.warn({ shop }, "Billing setup failed: plan name not provided");
      incrementCounter("billing.setup.validation_error", {
        shop,
        reason: "missing_plan_name",
      });
      return json(
        {
          success: false,
          error: "Plan name is required",
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
      logger.warn({ shop }, "Billing setup failed: shop not found");
      incrementCounter("billing.setup.validation_error", {
        shop,
        reason: "shop_not_found",
      });
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    // Get shop subscription
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: { shop_id: shopRecord.id },
      include: {
        subscription_plans: true,
      },
    });

    if (!shopSubscription) {
      return json(
        { success: false, error: "No subscription found" },
        { status: 400 },
      );
    }

    // Create Shopify recurring subscription using AppRecurringPricing
    const currency = shopRecord.currency_code || "USD";
    const appHandle = process.env.SHOPIFY_APP_HANDLE || "better-bundle-dev";
    const returnUrl = `https://admin.shopify.com/store/${shop}/apps/${appHandle}/app/billing`;

    const mutation = `
      mutation appSubscriptionCreate($name: String!, $returnUrl: URL!, $lineItems: [AppSubscriptionLineItemInput!]!, $trialDays: Int!, $test: Boolean!) {
        appSubscriptionCreate(
          name: $name
          returnUrl: $returnUrl
          lineItems: $lineItems
          trialDays: $trialDays
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
            createdAt
            currentPeriodEnd
            trialDays
            lineItems {
              id
              plan {
                pricingDetails {
                  __typename
                  ... on AppRecurringPricing {
                    price {
                      amount
                      currencyCode
                    }
                    interval
                  }
                }
              }
            }
          }
        }
      }
    `;

    const variables = {
      name: `Better Bundle - ${planName}`,
      returnUrl: returnUrl,
      test: process.env.NODE_ENV === "development",
      trialDays: trial,
      lineItems: [
        {
          plan: {
            appRecurringPricingDetails: {
              price: {
                amount: fee,
                currencyCode: currency,
              },
              interval: "EVERY_30_DAYS",
            },
          },
        },
      ],
    };

    const response = await admin.graphql(mutation, { variables });
    const result = await response.json();

    if (result.data?.appSubscriptionCreate?.userErrors?.length > 0) {
      const errors = result.data.appSubscriptionCreate.userErrors;
      logger.error(
        { errors, shop, planName },
        "Shopify errors while creating subscription",
      );
      incrementCounter("billing.setup.shopify_error", { shop, planName });
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
      logger.error(
        { shop, planName },
        "Billing setup failed: no subscription returned from Shopify",
      );
      incrementCounter("billing.setup.error", {
        shop,
        planName,
        reason: "no_subscription",
      });
      return json(
        { success: false, error: "Failed to create subscription" },
        { status: 500 },
      );
    }

    // Update shop subscription with Shopify subscription info
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        shopify_subscription_id: subscription.id,
        shopify_line_item_id: subscription.lineItems[0]?.id,
        confirmation_url: confirmationUrl,
        shopify_status: "PENDING",
        status: "PENDING_APPROVAL",
        updated_at: new Date(),
      },
    });

    logger.info(
      { shop, planName, fee, subscriptionId: subscription.id },
      "Billing setup completed successfully",
    );
    incrementCounter("billing.setup.completed", { shop, planName });

    return json({
      success: true,
      subscription_id: subscription.id,
      confirmationUrl: confirmationUrl,
      message: `Please approve the ${planName} plan ($${fee}/month) in Shopify`,
    });
  } catch (error) {
    logger.error({ error, shop, planName }, "Error in billing setup");
    incrementCounter("billing.setup.error", {
      shop,
      planName,
      reason: "exception",
    });
    return json(
      {
        success: false,
        error: "An internal error occurred. Please try again later.",
      },
      { status: 500 },
    );
  }
}
