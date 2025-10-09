import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function action({ request }: ActionFunctionArgs) {
  const { topic, shop, payload } = await authenticate.webhook(request);

  console.log(`💰 Billing success: ${topic} for shop ${shop}`);

  try {
    const billingAttempt = payload.subscription_billing_attempt;
    const subscriptionId = billingAttempt?.subscription_id;
    const amount = billingAttempt?.amount;
    const currency = billingAttempt?.currency;

    if (!subscriptionId) {
      console.error("❌ No billing attempt data in success webhook");
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

    // Create billing invoice record
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
      paid_at: new Date(), // Since this is a success webhook
      status: "paid" as const,
      description: `Billing invoice for subscription ${subscriptionId}`,
      line_items: billingAttempt.line_items || [],
      shopify_response: payload,
      payment_method: billingAttempt.payment_method || null,
      payment_reference: billingAttempt.payment_reference || null,
    };

    // Check if invoice already exists
    const existingInvoice = await prisma.billing_invoices.findFirst({
      where: {
        shopify_invoice_id: invoiceData.shopify_invoice_id,
      },
    });

    if (existingInvoice) {
      // Update existing invoice
      await prisma.billing_invoices.update({
        where: { id: existingInvoice.id },
        data: {
          amount_paid: invoiceData.amount_paid,
          status: "paid",
          paid_at: invoiceData.paid_at,
          payment_method: invoiceData.payment_method,
          payment_reference: invoiceData.payment_reference,
          shopify_response: invoiceData.shopify_response,
        },
      });
      console.log(
        `✅ Updated existing billing invoice ${invoiceData.shopify_invoice_id}`,
      );
    } else {
      // Create new invoice
      await prisma.billing_invoices.create({
        data: invoiceData,
      });
      console.log(
        `✅ Created new billing invoice ${invoiceData.shopify_invoice_id}`,
      );
    }

    console.log(
      `✅ Billing successful: $${amount} ${currency} for shop ${shop}`,
    );

    return json({ success: true });
  } catch (error) {
    console.error("❌ Error processing billing success:", error);
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}
