/**
 * Shopify Billing Webhook: charge_cancelled
 *
 * This webhook is triggered when a billing charge is cancelled by the shop owner or Shopify.
 * We use this to handle cancellations and potentially pause services.
 */

import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function action({ request }: ActionFunctionArgs) {
  const { topic, shop, payload } = await authenticate.webhook(request);

  console.log(`🔔 Billing webhook received: ${topic} for shop ${shop}`);

  try {
    // Parse the webhook payload
    const chargeData = payload.recurring_application_charge;

    if (!chargeData) {
      console.error("❌ No charge data in webhook payload");
      return json({ success: false, error: "No charge data" }, { status: 400 });
    }

    console.log("🚫 Charge cancelled:", {
      id: chargeData.id,
      name: chargeData.name,
      price: chargeData.price,
      currency: chargeData.currency,
      status: chargeData.status,
      shop: shop,
    });

    // Update billing invoice status
    const invoice = await prisma.billing_invoices.findFirst({
      where: {
        shop_id: shop,
        status: "pending",
        subtotal: parseFloat(chargeData.price),

        currency: chargeData.currency,
      },
      orderBy: {
        created_at: "desc",
      },
    });

    if (invoice) {
      // Update invoice with cancelled status
      await prisma.billing_invoices.update({
        where: { id: invoice.id },
        data: {
          status: "cancelled",
          payment_reference: chargeData.id.toString(),
          billing_metadata: {
            ...invoice,
            shopify_charge_id: chargeData.id,
            shopify_charge_status: chargeData.status,
            cancellation_reason: "Charge cancelled",
            webhook_received_at: new Date().toISOString(),
          },
        },
      });

      console.log(
        `🚫 Updated invoice ${invoice.id} as cancelled for Shopify charge ${chargeData.id}`,
      );
    } else {
      console.log(
        `⚠️ No matching invoice found for cancelled charge ${chargeData.id}`,
      );
    }

    // Update billing plan subscription status
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shop,
        status: "active",
      },
      orderBy: { created_at: "desc" },
    });

    if (billingPlan) {
      await prisma.billing_plans.update({
        where: { id: billingPlan.id },
        data: {
          subscription_status: "CANCELLED",
          subscription_cancelled_at: new Date(),
          configuration: {
            ...(billingPlan.configuration as any),
            subscription_status: "CANCELLED",
            subscription_cancelled_at: new Date().toISOString(),
            cancellation_reason: "Charge cancelled by merchant",
          },
        },
      });

      console.log(
        `🚫 Updated billing plan ${billingPlan.id} subscription status to CANCELLED`,
      );
    } else {
      console.log(`⚠️ No billing plan found for shop ${shop}`);
    }

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
