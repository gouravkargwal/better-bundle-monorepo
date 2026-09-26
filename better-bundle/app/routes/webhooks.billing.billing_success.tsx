import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import logger from "app/utils/logger";
import { processSuccessfulPayment } from "../services/dunning.service";
import { invalidateSuspensionCache } from "../middleware/serviceSuspension";
import { incrementCounter } from "../services/metrics.service";

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

    if (!billingAttempt || !billingAttempt.id) {
      logger.warn({ shop, payload }, "Missing billing attempt data in success webhook");
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
      select: { id: true, shop_domain: true },
    });

    if (!shopRecord) {
      logger.warn({ shop }, "No shop record found for domain");
      return json({ success: true });
    }

    // Find shop subscription (include metadata for dunning check)
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        is_active: true,
      },
      select: { id: true, shop_subscription_metadata: true },
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

    // Create billing invoice record
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
      paid_at: new Date(),
      status: "PAID" as const,
      description: `Billing invoice for subscription ${subscriptionId}`,
      line_items: billingAttempt.line_items || [],
      shopify_response: payload,
      payment_method: billingAttempt.payment_method || null,
      payment_reference: billingAttempt.payment_reference || null,
      usage_amount: usageAmount,
    };

    // ✅ RACE CONDITION PROTECTION: Use upsert to prevent duplicate processing
    await prisma.billing_invoices.upsert({
      where: {
        shopify_invoice_id: invoiceData.shopify_invoice_id,
      },
      update: {
        amount_paid: invoiceData.amount_paid,
        status: "PAID",
        paid_at: invoiceData.paid_at,
        payment_method: invoiceData.payment_method,
        payment_reference: invoiceData.payment_reference,
        shopify_response: invoiceData.shopify_response,
        billing_cycle_id: invoiceData.billing_cycle_id,
        usage_amount: invoiceData.usage_amount,
        updated_at: new Date(),
      },
      create: invoiceData as any,
    });

    incrementCounter("payment.success", {
      shop,
      subscriptionId: shopSubscription.id,
      amount,
      currency,
    });

    // --- Dunning State Machine: Reset on successful payment ---

    // Check if there's an active dunning period that needs resetting
    const metadata = shopSubscription.shop_subscription_metadata as Record<
      string,
      unknown
    > | null;
    const hasActiveDunning =
      metadata?.dunningState || metadata?.dunningFailureCount;

    if (hasActiveDunning) {
      processSuccessfulPayment();

      // Clear dunning state from subscription metadata
      await prisma.shop_subscriptions.update({
        where: { id: shopSubscription.id },
        data: {
          shop_subscription_metadata: {
            ...(metadata || {}),
            dunningState: null,
            dunningStartedAt: null,
            dunningFailureCount: 0,
            dunningUpdatedAt: null,
            dunningResetAt: new Date().toISOString(),
          },
        },
      });

      // If the shop was suspended due to payment failure, reactivate it
      if (shopRecord) {
        const shopData = await prisma.shops.findUnique({
          where: { id: shopRecord.id },
          select: { is_active: true, suspension_reason: true },
        });

        if (
          !shopData?.is_active &&
          shopData?.suspension_reason === "payment_failure"
        ) {
          logger.info(
            {
              shop,
              shopId: shopRecord.id,
              subscriptionId: shopSubscription.id,
            },
            "Reactivating shop after successful payment (dunning reset)",
          );

          await prisma.shops.update({
            where: { id: shopRecord.id },
            data: {
              is_active: true,
              suspension_reason: null,
              suspended_at: null,
            },
          });

          // Also reactivate the subscription
          await prisma.shop_subscriptions.update({
            where: { id: shopSubscription.id },
            data: {
              is_active: true,
              status: "ACTIVE",
            },
          });

          // Invalidate suspension cache
          await invalidateSuspensionCache(shopRecord.id);

          incrementCounter("payment.success.reactivation", {
            shop,
            subscriptionId: shopSubscription.id,
          });
        }
      }

      logger.info(
        {
          shop,
          shopId: shopRecord.id,
          subscriptionId: shopSubscription.id,
        },
        "Dunning state reset after successful payment",
      );
    }

    return json({ success: true });
  } catch (error) {
    logger.error({ error, shop }, "Error processing billing success");
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}
