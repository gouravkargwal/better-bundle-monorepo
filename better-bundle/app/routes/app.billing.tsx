import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { Page, Layout, BlockStack } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { BillingDashboard } from "../components/Billing/BillingDashboard";
import prisma from "../db.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Get shop record first to get the correct shop ID
    const shopRecord = await prisma.shop.findUnique({
      where: { shopDomain: shop },
      select: { id: true, currencyCode: true },
    });

    if (!shopRecord) {
      throw new Error("Shop not found. Please complete onboarding first.");
    }

    // Get billing plan using the correct shop ID
    const billingPlan = await prisma.billingPlan.findFirst({
      where: {
        shopId: shopRecord.id,
        status: "active",
      },
      orderBy: {
        effectiveFrom: "desc",
      },
      select: {
        id: true,
        shopId: true,
        shopDomain: true,
        name: true,
        type: true,
        status: true,
        configuration: true,
        effectiveFrom: true,
        effectiveUntil: true,
        createdAt: true,
        updatedAt: true,
      },
    });

    if (!billingPlan) {
      throw new Error(
        "No billing plan found. Please complete onboarding first.",
      );
    }

    // Get recent invoices
    const recentInvoices = await prisma.billingInvoice.findMany({
      where: {
        shopId: shopRecord.id,
      },
      orderBy: {
        createdAt: "desc",
      },
      take: 5,
    });

    // Get recent billing events
    const recentEvents = await prisma.billingEvent.findMany({
      where: {
        shopId: shopRecord.id,
      },
      orderBy: {
        occurredAt: "desc",
      },
      take: 10,
    });

    // Format the data to match the expected structure
    const billingData = {
      billing_plan: {
        id: billingPlan.id,
        name: billingPlan.name,
        type: billingPlan.type,
        status: billingPlan.status,
        configuration: billingPlan.configuration,
        effective_from: billingPlan.effectiveFrom.toISOString(),
        currency: shopRecord.currencyCode || "USD",
        trial_status: {
          is_trial_active:
            (billingPlan.configuration as any)?.trial_active || false,
          trial_threshold:
            (billingPlan.configuration as any)?.trial_threshold || 200,
          trial_revenue: (billingPlan.configuration as any)?.trial_revenue || 0,
          remaining_revenue: Math.max(
            0,
            ((billingPlan.configuration as any)?.trial_threshold || 200) -
              ((billingPlan.configuration as any)?.trial_revenue || 0),
          ),
          trial_progress:
            ((billingPlan.configuration as any)?.trial_threshold || 200) > 0
              ? (((billingPlan.configuration as any)?.trial_revenue || 0) /
                  ((billingPlan.configuration as any)?.trial_threshold ||
                    200)) *
                100
              : 0,
        },
      },
      recent_invoices: recentInvoices.map((invoice) => ({
        id: invoice.id,
        invoice_number: invoice.invoiceNumber,
        status: invoice.status,
        total: invoice.total,
        currency: invoice.currency,
        period_start: invoice.periodStart.toISOString(),
        period_end: invoice.periodEnd.toISOString(),
        due_date: invoice.dueDate.toISOString(),
        created_at: invoice.createdAt.toISOString(),
      })),
      recent_events: recentEvents.map((event) => ({
        id: event.id,
        type: event.type,
        data: event.data,
        occurred_at: event.occurredAt.toISOString(),
      })),
    };

    return json({
      shop,
      billingData,
    });
  } catch (error) {
    console.error("Error loading billing data:", error);
    throw new Error(
      error instanceof Error ? error.message : "Failed to load billing data",
    );
  }
};

export default function BillingPage() {
  const { billingData } = useLoaderData<typeof loader>();

  return (
    <Page>
      <TitleBar title="Billing" />
      <BlockStack gap="500">
        <Layout>
          <Layout.Section>
            <BillingDashboard billingData={billingData} />
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
