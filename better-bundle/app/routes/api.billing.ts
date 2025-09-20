/**
 * Billing API Routes
 *
 * This file contains API endpoints for billing-related operations
 * including billing status, invoices, and webhook handling.
 */

import {
  json,
  type LoaderFunctionArgs,
  type ActionFunctionArgs,
} from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

// ============= BILLING STATUS =============

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Get billing plan
    let billingPlan = await prisma.billingPlan.findFirst({
      where: {
        shopId: shop,
        status: "active",
      },
      orderBy: {
        effectiveFrom: "desc",
      },
    });

    // If no billing plan exists, create a trial plan
    if (!billingPlan) {
      console.log(`Creating trial billing plan for shop: ${shop}`);
      billingPlan = await prisma.billingPlan.create({
        data: {
          shopId: shop,
          shopDomain: shop, // You might want to get the actual domain
          name: "Free Trial Plan",
          type: "revenue_share",
          status: "active",
          configuration: {
            revenue_share_rate: 0.03,
            trial_threshold: 200.0,
            trial_active: true,
          },
          effectiveFrom: new Date(),
          isTrialActive: true,
          trialThreshold: 200.0,
          trialRevenue: 0.0,
        },
      });

      console.log(
        `Created trial billing plan ${billingPlan.id} for shop ${shop}`,
      );
    }

    // Get recent invoices
    const recentInvoices = await prisma.billingInvoice.findMany({
      where: {
        shopId: shop,
      },
      orderBy: {
        createdAt: "desc",
      },
      take: 5,
    });

    // Get recent billing events
    const recentEvents = await prisma.billingEvent.findMany({
      where: {
        shopId: shop,
      },
      orderBy: {
        occurredAt: "desc",
      },
      take: 10,
    });

    return json({
      success: true,
      data: {
        billing_plan: billingPlan
          ? {
              id: billingPlan.id,
              name: billingPlan.name,
              type: billingPlan.type,
              status: billingPlan.status,
              configuration: billingPlan.configuration,
              effective_from: billingPlan.effectiveFrom,
              trial_status: {
                is_trial_active: billingPlan.isTrialActive,
                trial_threshold: billingPlan.trialThreshold,
                trial_revenue: billingPlan.trialRevenue,
                remaining_revenue: Math.max(
                  0,
                  billingPlan.trialThreshold - billingPlan.trialRevenue,
                ),
                trial_progress:
                  billingPlan.trialThreshold > 0
                    ? (billingPlan.trialRevenue / billingPlan.trialThreshold) *
                      100
                    : 0,
              },
            }
          : null,
        recent_invoices: recentInvoices.map((invoice) => ({
          id: invoice.id,
          invoice_number: invoice.invoiceNumber,
          status: invoice.status,
          total: invoice.total,
          currency: invoice.currency,
          period_start: invoice.periodStart,
          period_end: invoice.periodEnd,
          due_date: invoice.dueDate,
          created_at: invoice.createdAt,
        })),
        recent_events: recentEvents.map((event) => ({
          id: event.id,
          type: event.type,
          data: event.data,
          occurred_at: event.occurredAt,
        })),
      },
    });
  } catch (error) {
    console.error("Error fetching billing status:", error);
    return json(
      {
        success: false,
        error: "Failed to fetch billing status",
      },
      { status: 500 },
    );
  }
}

// ============= BILLING WEBHOOK =============

export async function action({ request }: ActionFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    const body = await request.json();
    const { action: actionType, data } = body;

    switch (actionType) {
      case "process_webhook":
        return await handleBillingWebhook(shop, data);

      case "create_billing_plan":
        return await createBillingPlan(shop, data);

      case "update_billing_plan":
        return await updateBillingPlan(shop, data);

      default:
        return json(
          {
            success: false,
            error: "Invalid action",
          },
          { status: 400 },
        );
    }
  } catch (error) {
    console.error("Error processing billing action:", error);
    return json(
      {
        success: false,
        error: "Failed to process billing action",
      },
      { status: 500 },
    );
  }
}

// ============= WEBHOOK HANDLERS =============

async function handleBillingWebhook(shopId: string, webhookData: any) {
  try {
    // Create billing event for the webhook
    await prisma.billingEvent.create({
      data: {
        shopId: shopId,
        type: "shopify_webhook_received",
        data: webhookData,
        metadata: {
          processed_at: new Date().toISOString(),
          webhook_type: "billing",
        },
        occurredAt: new Date(),
      },
    });

    // Update invoice status if applicable
    if (webhookData.charge_id && webhookData.status) {
      const invoice = await prisma.billingInvoice.findFirst({
        where: {
          shopId: shopId,
          // Match by amount or other criteria
        },
      });

      if (invoice) {
        await prisma.billingInvoice.update({
          where: { id: invoice.id },
          data: {
            status: webhookData.status === "paid" ? "paid" : "pending",
            paidAt: webhookData.status === "paid" ? new Date() : null,
            paymentMethod: "shopify_billing",
            paymentReference: webhookData.charge_id,
          },
        });
      }
    }

    return json({
      success: true,
      message: "Webhook processed successfully",
    });
  } catch (error) {
    console.error("Error handling billing webhook:", error);
    return json(
      {
        success: false,
        error: "Failed to process webhook",
      },
      { status: 500 },
    );
  }
}

// ============= BILLING PLAN MANAGEMENT =============

async function createBillingPlan(shopId: string, planData: any) {
  try {
    const { name, type, configuration } = planData;

    // Create billing plan
    const billingPlan = await prisma.billingPlan.create({
      data: {
        shopId: shopId,
        shopDomain: shopId, // Assuming shopId is the domain
        name: name || "Pay-as-Performance Plan",
        type: type || "revenue_share",
        status: "active",
        configuration: configuration || {
          revenue_share_rate: 0.03,
          performance_tiers: [
            {
              name: "Tier 1",
              min_revenue: 0,
              max_revenue: 5000,
              rate: 0.03,
            },
            {
              name: "Tier 2",
              min_revenue: 5000,
              max_revenue: 25000,
              rate: 0.025,
            },
            {
              name: "Tier 3",
              min_revenue: 25000,
              max_revenue: null,
              rate: 0.02,
            },
          ],
          minimum_fee: 0,
          maximum_fee: null,
          currency: "USD",
          billing_cycle: "monthly",
        },
        effectiveFrom: new Date(),
      },
    });

    // Create billing event
    await prisma.billingEvent.create({
      data: {
        shopId: shopId,
        type: "plan_created",
        data: {
          plan_id: billingPlan.id,
          plan_type: billingPlan.type,
        },
        metadata: {
          created_by: "admin",
        },
        occurredAt: new Date(),
      },
    });

    return json({
      success: true,
      data: {
        plan_id: billingPlan.id,
        name: billingPlan.name,
        type: billingPlan.type,
        status: billingPlan.status,
        configuration: billingPlan.configuration,
      },
    });
  } catch (error) {
    console.error("Error creating billing plan:", error);
    return json(
      {
        success: false,
        error: "Failed to create billing plan",
      },
      { status: 500 },
    );
  }
}

async function updateBillingPlan(shopId: string, updateData: any) {
  try {
    const { plan_id, updates } = updateData;

    // Update billing plan
    const billingPlan = await prisma.billingPlan.update({
      where: {
        id: plan_id,
        shopId: shopId,
      },
      data: {
        ...updates,
        updatedAt: new Date(),
      },
    });

    // Create billing event
    await prisma.billingEvent.create({
      data: {
        shopId: shopId,
        type: "plan_updated",
        data: {
          plan_id: plan_id,
          updates: updates,
        },
        metadata: {
          updated_by: "admin",
        },
        occurredAt: new Date(),
      },
    });

    return json({
      success: true,
      data: {
        plan_id: billingPlan.id,
        name: billingPlan.name,
        type: billingPlan.type,
        status: billingPlan.status,
        configuration: billingPlan.configuration,
      },
    });
  } catch (error) {
    console.error("Error updating billing plan:", error);
    return json(
      {
        success: false,
        error: "Failed to update billing plan",
      },
      { status: 500 },
    );
  }
}

// ============= BILLING SUMMARY =============
