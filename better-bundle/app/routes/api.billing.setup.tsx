import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import {
  createShopSubscription,
  completeTrialAndCreateCycle,
} from "../services/billing.service";

export async function action({ request }: ActionFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Parse request body to get spending limit and monthly cap
    const body = await request.json();
    const spendingLimit = body.spendingLimit;
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

    // Check if shop already has an active subscription
    const existingSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        is_active: true,
      },
    });

    if (existingSubscription) {
      return json({
        success: false,
        error: "Active subscription already exists",
        existingSubscription: existingSubscription,
      });
    }

    // Check if shop has a trial subscription that needs to be completed
    const trialSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        status: "trial",
        is_active: true,
      },
      include: {
        subscription_trials: true,
      },
    });

    if (trialSubscription && trialSubscription.subscription_trials) {
      // Check if trial threshold is reached
      if (
        trialSubscription.subscription_trials.accumulated_revenue >=
        trialSubscription.subscription_trials.threshold_amount
      ) {
        // Complete trial and create first billing cycle
        await completeTrialAndCreateCycle(shopRecord.id);
      } else {
        return json(
          { success: false, error: "Trial threshold not reached yet" },
          { status: 400 },
        );
      }
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
        currency: shopRecord.currency_code,
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

    // Build return URL:
    // - Preferred: embedded admin path with your app handle
    // - Fallback: your app URL (Remix) which will re-embed automatically
    const storeSlug = shop.replace(".myshopify.com", "");
    const appHandle = process.env.SHOPIFY_APP_HANDLE;
    const embeddedReturnUrl = appHandle
      ? `https://admin.shopify.com/store/${storeSlug}/apps/${appHandle}/app/billing`
      : `${process.env.SHOPIFY_APP_URL}/app/billing?shop=${shop}`;

    const variables = {
      name: "Better Bundle - Usage Based",
      // Redirect back to embedded app route after approval (inside Admin)
      returnUrl: embeddedReturnUrl,
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

    console.log("📤 Creating Shopify subscription...");

    const response = await admin.graphql(mutation, { variables });
    const result = await response.json();

    console.log("📥 Shopify response:", JSON.stringify(result, null, 2));

    if (result.data?.appSubscriptionCreate?.userErrors?.length > 0) {
      const errors = result.data.appSubscriptionCreate.userErrors;
      console.error("❌ Shopify errors:", errors);
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

    console.log(`✅ Subscription created: ${subscription.id}`);

    // Create shop subscription using new schema
    const shopSubscription = await prisma.shop_subscriptions.create({
      data: {
        shop_id: shopRecord.id,
        subscription_plan_id: defaultPlan.id,
        pricing_tier_id: defaultPricingTier.id,
        status: "pending_approval",
        start_date: new Date(),
        is_active: true,
        auto_renew: true,
        user_chosen_cap_amount: monthlyCap, // Store user's chosen cap
      },
    });

    // Create Shopify subscription record
    const shopifySubscription = await prisma.shopify_subscriptions.create({
      data: {
        shop_subscription_id: shopSubscription.id,
        shopify_subscription_id: subscription.id,
        shopify_line_item_id: subscription.lineItems[0].id,
        confirmation_url: confirmationUrl,
        status: "PENDING",
        created_at: new Date(),
      },
    });

    console.log(`✅ New shop subscription created: ${shopSubscription.id}`);

    console.log(`✅ Billing setup complete for shop ${shop}`);

    return json({
      success: true,
      subscription_id: subscription.id,
      confirmation_url: confirmationUrl,
      message: "Please approve the subscription in Shopify",
    });
  } catch (error) {
    console.error("❌ Error in billing setup:", error);
    return json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
