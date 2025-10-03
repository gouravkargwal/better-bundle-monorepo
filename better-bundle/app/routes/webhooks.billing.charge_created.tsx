/**
 * Shopify Billing Webhook: app_subscriptions_update
 *
 * This webhook is triggered when a usage-based subscription is created, updated, or approved.
 * We use this to track subscription status changes and update our billing records.
 */

import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function action({ request }: ActionFunctionArgs) {
  const { topic, shop, payload } = await authenticate.webhook(request);

  console.log(`🔔 Subscription webhook received: ${topic} for shop ${shop}`);

  try {
    // Parse the webhook payload
    const subscriptionData = payload.app_subscription;

    if (!subscriptionData) {
      console.error("❌ No subscription data in webhook payload");
      return json(
        { success: false, error: "No subscription data" },
        { status: 400 },
      );
    }

    console.log("📋 Subscription updated:", {
      id: subscriptionData.id,
      name: subscriptionData.name,
      status: subscriptionData.status,
      shop: shop,
    });

    // Update billing plan with subscription status
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shop,
        status: "active",
      },
    });

    if (billingPlan) {
      // Update billing plan with subscription status
      await prisma.billing_plans.update({
        where: { id: billingPlan.id },
        data: {
          subscription_id: subscriptionData.id,
          subscription_status: subscriptionData.status,
          subscription_activated_at:
            subscriptionData.status === "ACTIVE" ? new Date() : null,
          configuration: {
            ...(billingPlan.configuration as any),
            subscription_id: subscriptionData.id,
            subscription_status: subscriptionData.status,
            subscription_updated_at: new Date().toISOString(),
            subscription_activated_at:
              subscriptionData.status === "ACTIVE"
                ? new Date().toISOString()
                : null,
          },
        },
      });

      console.log(
        `✅ Updated billing plan ${billingPlan.id} with subscription ${subscriptionData.id}`,
      );
    } else {
      console.log(`⚠️ No billing plan found for shop ${shop}`);
    }

    // Create billing event
    await prisma.billing_events.create({
      data: {
        shop_id: shop,
        type: "subscription_updated",
        data: {
          subscription_id: subscriptionData.id,
          name: subscriptionData.name,
          status: subscriptionData.status,
          updated_at: new Date().toISOString(),
        },
        billing_metadata: {
          webhook_topic: topic,
          shopify_subscription_id: subscriptionData.id,
        },
      },
    });

    console.log(`✅ Billing webhook processed successfully for shop ${shop}`);

    return json({ success: true });
  } catch (error) {
    console.error("❌ Error processing billing webhook:", error);
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}
