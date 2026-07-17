import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import logger from "app/utils/logger";

export async function action({ request }: ActionFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true },
    });

    if (!shopRecord) {
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    // Get shop subscription (single flat plan)
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: { shop_id: shopRecord.id },
      include: { subscription_plans: true },
    });

    if (!shopSubscription) {
      return json(
        { success: false, error: "No subscription found" },
        { status: 400 },
      );
    }

    if (shopSubscription.status === "ACTIVE") {
      return json(
        { success: false, error: "A subscription is already active." },
        { status: 400 },
      );
    }

    if (
      shopSubscription.status === "CANCELLED" ||
      shopSubscription.status === "EXPIRED"
    ) {
      return json(
        {
          success: false,
          error:
            "Your previous subscription was cancelled. Please start the billing setup from scratch.",
        },
        { status: 400 },
      );
    }

    const monthlyPrice = Number(
      shopSubscription.subscription_plans?.monthly_price ?? 99.0,
    );
    const trialDays = Number(shopSubscription.subscription_plans?.trial_days ?? 14);

    const mutation = `
      mutation appSubscriptionCreate($name: String!, $returnUrl: URL!, $lineItems: [AppSubscriptionLineItemInput!]!, $trialDays: Int, $test: Boolean!) {
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

    const appHandle = process.env.SHOPIFY_APP_HANDLE || "better-bundle-dev";
    const returnUrl = `https://admin.shopify.com/store/${shop}/apps/${appHandle}/app/billing`;

    const variables = {
      name: "BetterBundle",
      returnUrl,
      test: process.env.NODE_ENV === "development",
      trialDays,
      lineItems: [
        {
          plan: {
            appRecurringPricingDetails: {
              price: {
                amount: monthlyPrice,
                currencyCode: "USD",
              },
              interval: "EVERY_30_DAYS",
              discount: {
                durationLimitInIntervals: 1,
                value: { percentage: 0.5 },
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

    // Shopify subscription created — stay in TRIAL until the
    // APP_SUBSCRIPTIONS_UPDATE webhook confirms ACTIVE.
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        status: "TRIAL",
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
      confirmationUrl,
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
