/**
 * Create Usage-Based Subscription API
 *
 * This endpoint creates a usage-based subscription for a shop.
 * Called after the billing plan is created in the afterAuth hook.
 */

import {
  json,
  type LoaderFunctionArgs,
  type ActionFunctionArgs,
} from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function action({ request }: ActionFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    console.log(`🔄 Creating usage-based subscription for shop: ${shop}`);

    // Get shop information
    const shopInfo = await prisma.shop.findUnique({
      where: { shopDomain: shop },
      select: {
        id: true,
        accessToken: true,
        currencyCode: true,
        domain: true,
      },
    });

    if (!shopInfo) {
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    if (!shopInfo.accessToken) {
      return json(
        { success: false, error: "No access token" },
        { status: 400 },
      );
    }

    // Get billing plan
    const billingPlan = await prisma.billingPlan.findFirst({
      where: {
        shopId: shop,
        status: "active",
        type: "usage_based",
      },
    });

    if (!billingPlan) {
      return json(
        { success: false, error: "No usage-based billing plan found" },
        { status: 404 },
      );
    }

    // Create subscription via GraphQL API
    const mutation = `
      mutation appSubscriptionCreate($name: String!, $returnUrl: String!, $lineItems: [AppSubscriptionLineItemInput!]!) {
        appSubscriptionCreate(
          name: $name,
          returnUrl: $returnUrl,
          lineItems: $lineItems
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
            createdAt
            updatedAt
          }
        }
      }
    `;

    const variables = {
      name: "Better Bundle - Usage-Based Billing",
      returnUrl: `${process.env.SHOPIFY_APP_URL}/billing/return?shop=${shop}`,
      lineItems: [
        {
          plan: {
            appUsagePricingDetails: {
              terms: `3% of attributed revenue (max ${shopInfo.currencyCode === "USD" ? "$" : shopInfo.currencyCode}1000.00 per month)`,
              cappedAmount: {
                amount: 1000.0,
                currencyCode: shopInfo.currencyCode || "USD",
              },
            },
          },
        },
      ],
    };

    // Make GraphQL request to Shopify
    const response = await fetch(
      `https://${shop}/admin/api/2024-01/graphql.json`,
      {
        method: "POST",
        headers: {
          "X-Shopify-Access-Token": shopInfo.accessToken,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: mutation,
          variables: variables,
        }),
      },
    );

    const result = await response.json();

    if (result.errors) {
      console.error("GraphQL errors:", result.errors);
      return json(
        { success: false, error: "GraphQL errors", details: result.errors },
        { status: 400 },
      );
    }

    const data = result.data?.appSubscriptionCreate;

    if (data?.userErrors?.length > 0) {
      console.error("User errors:", data.userErrors);
      return json(
        { success: false, error: "User errors", details: data.userErrors },
        { status: 400 },
      );
    }

    if (!data?.appSubscription) {
      return json(
        { success: false, error: "No subscription created" },
        { status: 400 },
      );
    }

    const subscription = data.appSubscription;

    // Update billing plan with subscription data
    await prisma.billingPlan.update({
      where: { id: billingPlan.id },
      data: {
        configuration: {
          ...billingPlan.configuration,
          subscription_id: subscription.id,
          subscription_status: subscription.status,
          line_items: subscription.lineItems,
          subscription_created_at: new Date().toISOString(),
          subscription_pending: false,
        },
      },
    });

    // Create billing event
    await prisma.billingEvent.create({
      data: {
        shopId: shop,
        type: "subscription_created",
        data: {
          subscription_id: subscription.id,
          name: subscription.name,
          status: subscription.status,
          confirmation_url: data.confirmationUrl,
          created_at: subscription.createdAt,
        },
        metadata: {
          subscription_id: subscription.id,
          event_type: "subscription_creation",
        },
      },
    });

    console.log(`✅ Created subscription ${subscription.id} for shop ${shop}`);

    return json({
      success: true,
      subscription: {
        id: subscription.id,
        name: subscription.name,
        status: subscription.status,
        confirmation_url: data.confirmationUrl,
        line_items: subscription.lineItems,
      },
    });
  } catch (error) {
    console.error("Error creating subscription:", error);
    return json(
      { success: false, error: "Failed to create subscription" },
      { status: 500 },
    );
  }
}

export async function loader({ request }: LoaderFunctionArgs) {
  return json({ message: "Use POST to create subscription" }, { status: 405 });
}
