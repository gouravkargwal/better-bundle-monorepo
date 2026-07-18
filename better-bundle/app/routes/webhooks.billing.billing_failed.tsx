import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import logger from "../utils/logger";
import { invalidateSuspensionCache } from "../middleware/serviceSuspension";
import { logSuspensionEvent } from "../services/suspensionAudit.service";
import { incrementCounter } from "../services/metrics.service";
import {
  processPaymentFailure,
  type DunningInfo,
  type DunningState,
} from "../services/dunning.service";

export async function action({ request }: ActionFunctionArgs) {
  const { topic, shop, payload } = await authenticate.webhook(request);

  try {
    const billingAttempt = payload.subscription_billing_attempt;
    const subscriptionId = billingAttempt?.subscription_id;
    const amount = billingAttempt?.amount;
    const currency = billingAttempt?.currency;
    const failureReason = billingAttempt?.failure_reason;

    if (!subscriptionId) {
      logger.error({ shop }, "No billing attempt data in failed webhook");
      return json(
        { success: false, error: "No billing data" },
        { status: 400 },
      );
    }

    // Find shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, shop_domain: true, email: true },
    });

    if (!shopRecord) {
      logger.warn({ shop }, "No shop record found for domain");
      return json({ success: true });
    }

    // Find shop subscription
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        is_active: true,
      },
      select: { id: true, status: true, shop_subscription_metadata: true },
    });

    if (!shopSubscription) {
      logger.warn({ shop }, "No active subscription found for shop");
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
      status: "FAILED" as const,
      description: `Failed billing invoice for subscription ${subscriptionId} - ${failureReason}`,
      line_items: billingAttempt.line_items || [],
      shopify_response: payload,
      payment_method: billingAttempt.payment_method || null,
      payment_reference: billingAttempt.payment_reference || null,
      failure_reason: failureReason,
    };

    await prisma.billing_invoices.upsert({
      where: {
        shopify_invoice_id: invoiceData.shopify_invoice_id,
      },
      update: {
        status: "FAILED",
        failure_reason: failureReason,
        shopify_response: invoiceData.shopify_response,
        updated_at: new Date(),
      },
      create: invoiceData,
    });

    // Count failed invoices for this subscription
    const failedCount = await prisma.billing_invoices.count({
      where: {
        shop_subscription_id: shopSubscription.id,
        status: "FAILED",
      },
    });

    // --- Dunning State Machine Integration ---

    // Read existing dunning info from subscription metadata
    const metadata = shopSubscription.shop_subscription_metadata as Record<
      string,
      unknown
    > | null;
    const existingDunning: DunningInfo = {
      state: (metadata?.dunningState as DunningState) || null,
      startedAt: metadata?.dunningStartedAt
        ? new Date(metadata.dunningStartedAt as string)
        : null,
      failureCount: (metadata?.dunningFailureCount as number) || 0,
    };

    // Process payment failure through the dunning state machine
    const dunningResult = processPaymentFailure(existingDunning);

    // Log dunning state transition
    logger.info(
      {
        shop,
        shopId: shopRecord.id,
        subscriptionId: shopSubscription.id,
        failureCount:
          dunningResult.daysSinceStart === 0 ? failedCount : failedCount,
        dunningState: dunningResult.newState,
        shouldSuspend: dunningResult.shouldSuspend,
        daysSinceStart: dunningResult.daysSinceStart,
      },
      `Dunning state transition: ${existingDunning.state || "NONE"} → ${dunningResult.newState}`,
    );

    // Update subscription metadata with new dunning state
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        shop_subscription_metadata: {
          ...(metadata || {}),
          dunningState: dunningResult.newState,
          dunningStartedAt:
            metadata?.dunningStartedAt || new Date().toISOString(),
          dunningFailureCount: failedCount,
          dunningUpdatedAt: new Date().toISOString(),
        },
      },
    });

    // Trigger suspension if the dunning state machine indicates it
    if (dunningResult.shouldSuspend) {
      logger.info(
        {
          shop,
          failedCount,
          subscriptionId: shopSubscription.id,
          dunningState: dunningResult.newState,
          daysSinceStart: dunningResult.daysSinceStart,
        },
        `Dunning period complete — suspending shop due to unresolved payment failures`,
      );

      // Update subscription status to SUSPENDED
      await prisma.shop_subscriptions.update({
        where: { id: shopSubscription.id },
        data: {
          status: "SUSPENDED",
          is_active: false,
        },
      });

      // Suspend the shop
      await prisma.shops.update({
        where: { id: shopRecord.id },
        data: {
          is_active: false,
          suspension_reason: "payment_failure",
          suspended_at: new Date(),
        },
      });

      // Log the suspension event to the audit trail
      await logSuspensionEvent({
        shopId: shopRecord.id,
        action: "SUSPENDED",
        reason: "payment_failure",
        triggeredBy: "webhook",
        metadata: {
          failureCount: failedCount,
          subscriptionId: shopSubscription.id,
        },
      });

      // Invalidate Redis suspension cache so subsequent checks pick up the change
      await invalidateSuspensionCache(shopRecord.id);

      // Log structured suspension event
      logger.info(
        {
          shop,
          shopId: shopRecord.id,
          subscriptionId: shopSubscription.id,
          failedCount,
          dunningState: dunningResult.newState,
          daysSinceStart: dunningResult.daysSinceStart,
          reason: "payment_failure",
        },
        "Shop suspended due to unresolved payment failures after dunning period",
      );

      incrementCounter("payment_failure.suspension", {
        shop,
        subscriptionId: shopSubscription.id,
        failureCount: failedCount,
      });
    }

    incrementCounter("payment_failure.occurred", {
      shop,
      subscriptionId: shopSubscription.id,
      failureCount: failedCount,
    });

    return json({ success: true });
  } catch (error) {
    logger.error({ error, shop }, "Error processing billing failure");
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}
