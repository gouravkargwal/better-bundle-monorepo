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

  try {
    const body = await request.json();
    planName = body.planName;

    logger.info({ shop, planName }, "Billing setup started");

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

    // Pricing terms come from the plan, never from the request body — the
    // client must not be able to name its own commission rate or cap.
    const plan = shopSubscription.subscription_plans;
    const commissionRate = Number(
      shopSubscription.commission_rate_override ?? plan?.commission_rate ?? 0.03,
    );
    const cappedAmount = Number(
      shopSubscription.cap_amount_override ?? plan?.cap_amount ?? 299,
    );

    const currency = shopRecord.currency_code || "USD";
    const appHandle = process.env.SHOPIFY_APP_HANDLE || "better-bundle-dev";
    const returnUrl = `https://admin.shopify.com/store/${shop}/apps/${appHandle}/app/billing`;

    // AppUsagePricing, not AppRecurringPricing: there is no fixed monthly fee.
    // `terms` is shown to the merchant on the approval screen, and cappedAmount
    // is the ceiling Shopify enforces — usage records beyond it are rejected.
    //
    // No trialDays here. The trial is a revenue threshold tracked in our own
    // database, and a Shopify trial would only delay charges by a clock we do
    // not bill on.
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
            createdAt
            currentPeriodEnd
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
                    balanceUsed {
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

    const ratePercent = (commissionRate * 100).toFixed(1).replace(/\.0$/, "");
    const variables = {
      name: `Better Bundle - ${planName}`,
      returnUrl: returnUrl,
      test: process.env.NODE_ENV === "development",
      lineItems: [
        {
          plan: {
            appUsagePricingDetails: {
              terms: `${ratePercent}% of revenue attributed to recommendations, up to ${cappedAmount} ${currency} per 30 days`,
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
      {
        shop,
        planName,
        commissionRate,
        cappedAmount,
        subscriptionId: subscription.id,
      },
      "Billing setup completed successfully",
    );
    incrementCounter("billing.setup.completed", { shop, planName });

    return json({
      success: true,
      subscription_id: subscription.id,
      confirmationUrl: confirmationUrl,
      message: `Please approve ${ratePercent}% of attributed revenue (max ${cappedAmount} ${currency}/30 days) in Shopify`,
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
