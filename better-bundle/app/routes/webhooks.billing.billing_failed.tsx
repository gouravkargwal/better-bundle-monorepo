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

function sumUsageAmount(lineItems: unknown[]): number {
  if (!Array.isArray(lineItems) || lineItems.length === 0) return 0;

  let total = 0;
  let foundUsageType = false;

  for (const item of lineItems) {
    const pricingDetails = (item as Record<string, unknown>)?.plan as Record<string, unknown> | undefined;
    const details = pricingDetails?.pricingDetails as Record<string, unknown> | undefined;
    if (details?.__typename === "AppUsagePricing") {
      foundUsageType = true;
      const amountRaw = (item as Record<string, unknown>)?.amount;
      const amount = typeof amountRaw === "string"
        ? parseFloat(amountRaw)
        : typeof amountRaw === "number"
          ? amountRaw
          : parseFloat(((amountRaw as Record<string, unknown>)?.amount as string) || "0");
      if (!Number.isNaN(amount)) {
        total += amount;
      }
    }
  }

  if (!foundUsageType) {
    logger.warn(
      { lineItemCount: lineItems.length },
      "No AppUsagePricing line items found; falling back to summing all line items",
    );
    for (const item of lineItems) {
      const amountRaw = (item as Record<string, unknown>)?.amount;
      const amount = typeof amountRaw === "string"
        ? parseFloat(amountRaw)
        : typeof amountRaw === "number"
          ? amountRaw
          : parseFloat(((amountRaw as Record<string, unknown>)?.amount as string) || "0");
      if (!Number.isNaN(amount)) {
        total += amount;
      }
    }
  }

  return total;
}

export async function action({ request }: ActionFunctionArgs) {
  const { topic, shop, payload } = await authenticate.webhook(request);

  try {
    const billingAttempt = payload.subscription_billing_attempt;
    const subscriptionId = billingAttempt?.subscription_id;
    const amount = billingAttempt?.amount;
    const currency = billingAttempt?.currency;
    const failureReason = billingAttempt?.failure_reason;

    if (!billingAttempt || !billingAttempt.id) {
      logger.warn({ shop, payload }, "Missing billing attempt data in failed webhook");
      return json({ success: true });
    }

    if (!subscriptionId) {
      logger.warn({ shop, attemptId: billingAttempt.id }, "No subscription_id in billing attempt");
      return json({ success: true });
    }

    const createdAt = billingAttempt.created_at ? new Date(billingAttempt.created_at) : new Date();
    if (Number.isNaN(createdAt.getTime())) {
      logger.warn({ shop, attemptId: billingAttempt.id }, "Malformed created_at in billing attempt");
      return json({ success: true });
    }

    const dueDate = billingAttempt.due_date ? new Date(billingAttempt.due_date) : null;
    if (dueDate && Number.isNaN(dueDate.getTime())) {
      logger.warn({ shop, attemptId: billingAttempt.id }, "Malformed due_date in billing attempt");
      return json({ success: true });
    }

    const currentPeriodStartRaw = billingAttempt.currentPeriodStart || billingAttempt.current_period_start;
    const currentPeriodEndRaw = billingAttempt.currentPeriodEnd || billingAttempt.current_period_end;
    const currentPeriodStart = currentPeriodStartRaw ? new Date(currentPeriodStartRaw) : null;
    const currentPeriodEnd = currentPeriodEndRaw ? new Date(currentPeriodEndRaw) : null;

    if (currentPeriodStart && Number.isNaN(currentPeriodStart.getTime())) {
      logger.warn({ shop, attemptId: billingAttempt.id }, "Malformed currentPeriodStart in billing attempt");
      return json({ success: true });
    }
    if (currentPeriodEnd && Number.isNaN(currentPeriodEnd.getTime())) {
      logger.warn({ shop, attemptId: billingAttempt.id }, "Malformed currentPeriodEnd in billing attempt");
      return json({ success: true });
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

    // Look up or create billing cycle for this period
    let billingCycleId: string | null = null;

    if (currentPeriodStart && currentPeriodEnd) {
      let cycle = await prisma.billing_cycles.findFirst({
        where: {
          shop_subscription_id: shopSubscription.id,
          start_date: currentPeriodStart,
        },
      });

      if (!cycle) {
        const maxCycleNumberResult = await prisma.billing_cycles.findFirst({
          where: { shop_subscription_id: shopSubscription.id },
          orderBy: { cycle_number: "desc" },
          select: { cycle_number: true },
        });

        const nextCycleNumber = (maxCycleNumberResult?.cycle_number ?? 0) + 1;

        await prisma.$executeRaw`
          INSERT INTO billing_cycles (
            shop_subscription_id, cycle_number, start_date, end_date, status, activated_at
          )
          VALUES (
            ${shopSubscription.id},
            ${nextCycleNumber},
            ${currentPeriodStart},
            ${currentPeriodEnd},
            'active',
            NOW()
          )
          ON CONFLICT (shop_subscription_id, start_date) DO NOTHING
        `;

        cycle = await prisma.billing_cycles.findFirst({
          where: {
            shop_subscription_id: shopSubscription.id,
            start_date: currentPeriodStart,
          },
        });
      }

      billingCycleId = cycle?.id ?? null;
    }

    const usageAmount = sumUsageAmount(Array.isArray(billingAttempt.line_items) ? billingAttempt.line_items : []);

    // Create or update billing invoice record with failed status
    const invoiceData = {
      shop_id: shopRecord.id,
      shop_subscription_id: shopSubscription.id,
      billing_cycle_id: billingCycleId,
      shopify_invoice_id:
        billingAttempt.id?.toString() || `invoice_${Date.now()}`,
      invoice_number: billingAttempt.invoice_number || null,
      amount_due: parseFloat(billingAttempt.amount_due || "0"),
      amount_paid: parseFloat(billingAttempt.amount_paid || "0"),
      total_amount: parseFloat(amount || "0"),
      currency: currency || "USD",
      invoice_date: createdAt,
      due_date: dueDate,
      paid_at: null, // No payment since it failed
      status: "FAILED" as const,
      description: `Failed billing invoice for subscription ${subscriptionId} - ${failureReason}`,
      line_items: billingAttempt.line_items || [],
      shopify_response: payload,
      payment_method: billingAttempt.payment_method || null,
      payment_reference: billingAttempt.payment_reference || null,
      failure_reason: failureReason,
      usage_amount: usageAmount,
    };

    await prisma.billing_invoices.upsert({
      where: {
        shopify_invoice_id: invoiceData.shopify_invoice_id,
      },
      update: {
        status: "FAILED",
        failure_reason: failureReason,
        shopify_response: invoiceData.shopify_response,
        billing_cycle_id: invoiceData.billing_cycle_id,
        usage_amount: invoiceData.usage_amount,
        updated_at: new Date(),
      },
      create: invoiceData as any,
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
        failureCount: failedCount,
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
