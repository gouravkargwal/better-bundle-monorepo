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

    // ✅ Get shop subscription
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

    // Validate subscription can proceed to billing setup.
    // Allowed statuses: PENDING_APPROVAL (trial completed, ready for approval)
    // Not allowed: TRIAL (must complete trial first), ACTIVE (already active),
    // CANCELLED/EXPIRED (must go through fresh setup).
    if (shopSubscription.status === "TRIAL") {
      return json(
        {
          success: false,
          error:
            "Your trial is still active. Please complete the trial before setting up billing.",
        },
        { status: 400 },
      );
    }

    if (shopSubscription.status === "ACTIVE") {
      return json(
        {
          success: false,
          error: "A subscription is already active.",
        },
        { status: 400 },
      );
    }

    if (shopSubscription.status === "CANCELLED" || shopSubscription.status === "EXPIRED") {
      return json(
        {
          success: false,
          error:
            "Your previous subscription was cancelled. Please start the billing setup from scratch.",
        },
        { status: 400 },
      );
    }

    // Validate trial threshold was reached before allowing billing setup
    const trialRevenue = Number(shopSubscription.trial_revenue || 0);
    const thresholdAmount = Number(
      shopSubscription.trial_threshold_override ||
        shopSubscription.pricing_tiers?.trial_threshold_amount ||
        0,
    );

    if (trialRevenue < thresholdAmount) {
      return json(
        {
          success: false,
          error:
            "Trial threshold not reached. Please complete your trial first.",
        },
        { status: 400 },
      );
    }

    // ✅ No need to check existing Shopify subscriptions - we fetch status from Shopify API in real-time

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

    const commissionRate = Number(
      shopSubscription.pricing_tiers?.commission_rate || 0.03,
    );
    const commissionRatePct = (commissionRate * 100).toFixed(1);

    const variables = {
      name: "Better Bundle - Usage Based",
      // Redirect back to app after approval
      returnUrl: returnUrl,
      test: process.env.NODE_ENV === "development",
      lineItems: [
        {
          plan: {
            appUsagePricingDetails: {
              terms: `${commissionRatePct}% of attributed revenue (capped at $${cappedAmount}/month)`,
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

    // Shopify subscription created — store the IDs but keep status as TRIAL.
    // PENDING_APPROVAL has been removed — the merchant stays in TRIAL until the
    // APP_SUBSCRIPTIONS_UPDATE webhook confirms ACTIVE.
    // The UI checks confirmation_url to show the approval button.
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        status: "TRIAL", // Stay in TRIAL — confirmation_url handles the pending state
        user_chosen_cap_amount: monthlyCap,
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
