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
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, currency_code: true },
    });

    if (!shopRecord) {
      throw new Error("Shop not found. Please complete onboarding first.");
    }

    // Get billing plan using the correct shop ID
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shopRecord.id,
        status: "active",
      },
      orderBy: {
        effective_from: "desc",
      },
      select: {
        id: true,
        shop_id: true,
        shop_domain: true,
        name: true,
        type: true,
        status: true,
        configuration: true,
        effective_from: true,
        effective_until: true,
        created_at: true,
        updated_at: true,
        trial_revenue: true,
        trial_threshold: true,
        is_trial_active: true,
      },
    });

    if (!billingPlan) {
      throw new Error(
        "No billing plan found. Please complete onboarding first.",
      );
    }

    // Get recent invoices
    const recentInvoices = await prisma.billing_invoices.findMany({
      where: {
        shop_id: shopRecord.id,
      },
      orderBy: {
        created_at: "desc",
      },
      take: 5,
    });

    // Get recent billing events
    const recentEvents = await prisma.billing_events.findMany({
      where: {
        shop_id: shopRecord.id,
      },
      orderBy: {
        occurred_at: "desc",
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
        effective_from: billingPlan.effective_from.toISOString(),
        currency: shopRecord.currency_code,
        trial_status: {
          is_trial_active: billingPlan.is_trial_active || false,
          trial_threshold: Number(billingPlan.trial_threshold) || 200,
          trial_revenue: Number(billingPlan.trial_revenue) || 0,
          remaining_revenue: Math.max(
            0,
            (Number(billingPlan.trial_threshold) || 200) -
              (Number(billingPlan.trial_revenue) || 0),
          ),
          trial_progress:
            (Number(billingPlan.trial_threshold) || 200) > 0
              ? ((Number(billingPlan.trial_revenue) || 0) /
                  (Number(billingPlan.trial_threshold) || 200)) *
                100
              : 0,
        },
      },
      recent_invoices: recentInvoices.map((invoice) => ({
        id: invoice.id,
        invoice_number: invoice.invoice_number,
        status: invoice.status,
        total: invoice.total,
        currency: invoice.currency,
        period_start: invoice.period_start.toISOString(),
        period_end: invoice.period_end.toISOString(),
        due_date: invoice.due_date.toISOString(),
        created_at: invoice.created_at.toISOString(),
      })),
      recent_events: recentEvents.map((event) => ({
        id: event.id,
        type: event.type,
        data: event.data,
        occurred_at: event.occurred_at.toISOString(),
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
