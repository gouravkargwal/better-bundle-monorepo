import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import logger from "app/utils/logger";

export async function action({ request }: ActionFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Parse request body — now expects planName and monthlyFee instead of monthlyCap
    const body = await request.json();
    const { planName, monthlyFee, trialDays } = body;

    // Validate inputs
    const fee = Number(monthlyFee) || 29;
    const trial = Number(trialDays) || 14;

    if (!planName) {
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
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    // Get shop subscription
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: { shop_id: shopRecord.id },
      include: {
        pricing_tiers: true,
        subscription_plans: true,
      },
    });

    if (!shopSubscription) {
      return json(
        { success: false, error: "No subscription found" },
        { status: 400 },
      );
    }

    // Get flat fee plan from database for pricing details
    const pricingTier = await prisma.pricing_tiers.findFirst({
      where: {
        currency: shopRecord.currency_code || "USD",
        is_active: true,
        subscription_plans: {
          is_active: true,
          plan_type: "FLAT_RATE",
        },
      },
      include: {
        subscription_plans: true,
      },
    });

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

    return json({
      success: true,
      subscription_id: subscription.id,
      confirmationUrl: confirmationUrl,
      message: `Please approve the ${planName} plan ($${fee}/month) in Shopify`,
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
