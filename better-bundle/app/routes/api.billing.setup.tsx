import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function action({ request }: ActionFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Parse request body to get spending limit
    const body = await request.json();
    const spendingLimit = body.spendingLimit || 1000.0;

    console.log(
      `🔄 Starting billing setup for shop ${shop} with spending limit: $${spendingLimit}`,
    );

    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, currency_code: true },
    });

    if (!shopRecord) {
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    // Get billing plan
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shopRecord.id,
        status: { in: ["active", "suspended"] },
      },
    });

    if (!billingPlan) {
      return json(
        { success: false, error: "No billing plan found" },
        { status: 404 },
      );
    }

    // Check if trial is completed
    if (billingPlan.is_trial_active) {
      return json(
        { success: false, error: "Trial still active" },
        { status: 400 },
      );
    }

    // Check if subscription already exists
    if (billingPlan.subscription_id) {
      // Already has subscription, check status
      if (billingPlan.subscription_status === "ACTIVE") {
        return json({
          success: true,
          message: "Subscription already active",
          subscription_id: billingPlan.subscription_id,
        });
      } else if (billingPlan.subscription_status === "PENDING") {
        return json({
          success: true,
          message: "Subscription pending approval",
          subscription_id: billingPlan.subscription_id,
          confirmation_url: billingPlan.subscription_confirmation_url,
        });
      }
    }

    // Create Shopify subscription using GraphQL
    const currency = shopRecord.currency_code || "USD";
    const cappedAmount = spendingLimit; // User-selected monthly cap

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

    // Update billing plan
    await prisma.billing_plans.updateMany({
      where: { id: billingPlan.id },
      data: {
        subscription_id: subscription.id,
        subscription_status: "PENDING",
        subscription_line_item_id: subscription.lineItems[0].id,
        subscription_confirmation_url: confirmationUrl,
        requires_subscription_approval: true,
        configuration: {
          ...(billingPlan.configuration as any),
          subscription_id: subscription.id,
          subscription_status: "PENDING",
          subscription_created_at: new Date().toISOString(),
          capped_amount: cappedAmount,
          currency: currency,
        },
      },
    });

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
