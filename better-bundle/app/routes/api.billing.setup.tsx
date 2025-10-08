import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
// Removed unused imports

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

    // ✅ Get shop subscription - only allow if trial is completed
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        is_active: true,
        // ✅ Only allow if trial is completed
        status: "TRIAL_COMPLETED",
      },
    });

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

    // ✅ UPDATE: Change status from TRIAL_COMPLETED to PENDING_APPROVAL
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        status: "pending_approval", // ✅ NOW we set PENDING_APPROVAL
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
        status: "pending",
        created_at: new Date(),
        error_count: "0", // Required field
      },
    });

    console.log(`✅ Shop subscription updated: ${shopSubscription.id}`);

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
