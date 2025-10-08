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

    console.log(
      `❌ Billing failed: $${amount} ${currency} - Reason: ${failureReason}`,
    );

    // You can add logic here to:
    // - Update billing records with failure
    // - Send failure notification emails
    // - Implement retry logic
    // - Suspend services if needed

    return json({ success: true });
  } catch (error) {
    console.error("❌ Error processing billing failure:", error);
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}
