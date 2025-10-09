import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function action({ request }: ActionFunctionArgs) {
  const { topic, shop, payload } = await authenticate.webhook(request);

  console.log(`💸 Billing failed: ${topic} for shop ${shop}`);

  try {
    const billingAttempt = payload.subscription_billing_attempt;
    const subscriptionId = billingAttempt?.subscription_id;
    const amount = billingAttempt?.amount;
    const currency = billingAttempt?.currency;
    const failureReason = billingAttempt?.failure_reason;

    if (!subscriptionId) {
      console.error("❌ No billing attempt data in failed webhook");
      return json(
        { success: false, error: "No billing data" },
        { status: 400 },
      );
    }

    // Find shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, shop_domain: true },
    });

    if (!shopRecord) {
      console.log(`⚠️ No shop record found for domain ${shop}`);
      return json({ success: true });
    }

    // Find shop subscription
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        is_active: true,
      },
      select: { id: true },
    });

    if (!shopSubscription) {
      console.log(`⚠️ No active subscription found for shop ${shop}`);
      return json({ success: true });
    }

    // Create or update billing invoice record with failed status
    const invoiceData = {
      shop_subscription_id: shopSubscription.id,
      shopify_invoice_id:
        billingAttempt.id?.toString() || `invoice_${Date.now()}`,
      invoice_number: billingAttempt.invoice_number || null,
      amount_due: parseFloat(billingAttempt.amount_due || "0"),
      amount_paid: parseFloat(billingAttempt.amount_paid || "0"),
      total_amount: parseFloat(amount || "0"),
      currency: currency || "USD",
      invoice_date: new Date(billingAttempt.created_at || new Date()),
      due_date: billingAttempt.due_date
        ? new Date(billingAttempt.due_date)
        : null,
      paid_at: null, // No payment since it failed
      status: "failed" as const,
      description: `Failed billing invoice for subscription ${subscriptionId} - ${failureReason}`,
      line_items: billingAttempt.line_items || [],
      shopify_response: payload,
      payment_method: billingAttempt.payment_method || null,
      payment_reference: billingAttempt.payment_reference || null,
      failure_reason: failureReason,
    };

    // Check if invoice already exists
    const existingInvoice = await prisma.billing_invoices.findFirst({
      where: {
        shopify_invoice_id: invoiceData.shopify_invoice_id,
      },
    });

    if (existingInvoice) {
      // Update existing invoice with failure status
      await prisma.billing_invoices.update({
        where: { id: existingInvoice.id },
        data: {
          status: "failed",
          failure_reason: failureReason,
          shopify_response: invoiceData.shopify_response,
        },
      });
      console.log(
        `❌ Updated existing billing invoice ${invoiceData.shopify_invoice_id} with failure status`,
      );
    } else {
      // Create new failed invoice
      await prisma.billing_invoices.create({
        data: invoiceData,
      });
      console.log(
        `❌ Created new failed billing invoice ${invoiceData.shopify_invoice_id}`,
      );
    }

    console.log(
      `❌ Billing failed: $${amount} ${currency} - Reason: ${failureReason}`,
    );

    return json({ success: true });
  } catch (error) {
    console.error("❌ Error processing billing failure:", error);
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}
