import {
  json,
  type LoaderFunctionArgs,
  type ActionFunctionArgs,
} from "@remix-run/node";
import {
  useLoaderData,
  useActionData,
  useNavigation,
  useSubmit,
} from "@remix-run/react";
import { authenticate } from "../shopify.server";
import {
  Page,
  Layout,
  BlockStack,
  Banner,
  Button,
  InlineStack,
  Icon,
  Text,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { BillingDashboard } from "../components/Billing/BillingDashboard";
import { BillingSetup } from "../components/Billing/BillingSetup";
import { TrialCompletionNotification } from "../components/Notifications/TrialCompletionNotification";
import { handleTrialCompletion } from "../services/shop.service";
import prisma from "../db.server";
import { CreditCardIcon, CheckCircleIcon } from "@shopify/polaris-icons";

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

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session, admin } = await authenticate.admin(request);
  const { shop } = session;

  try {
    const formData = await request.formData();
    const action = formData.get("action");

    if (action === "setup_billing") {
      // Get shop record
      const shopRecord = await prisma.shops.findUnique({
        where: { shop_domain: shop },
        select: { id: true, currency_code: true },
      });

      if (!shopRecord) {
        return json(
          { success: false, error: "Shop not found" },
          { status: 400 },
        );
      }

      // Get current billing plan
      const billingPlan = await prisma.billing_plans.findFirst({
        where: {
          shop_id: shopRecord.id,
          status: "active",
        },
      });

      if (!billingPlan) {
        return json(
          { success: false, error: "No billing plan found" },
          { status: 400 },
        );
      }

      // Check if trial is completed and billing setup is needed
      const config = billingPlan.configuration as any;
      const isTrialCompleted =
        !billingPlan.is_trial_active && config?.trial_completed_at;
      const needsBillingSetup =
        config?.subscription_required && !config?.subscription_id;

      if (isTrialCompleted && needsBillingSetup) {
        // Handle trial completion with subscription creation
        const result = await handleTrialCompletion(
          session,
          admin,
          shopRecord.id,
          shop,
          Number(billingPlan.trial_revenue) || 0,
          shopRecord.currency_code || "USD",
        );

        if (result.success && result.subscription_created) {
          return json({
            success: true,
            message: "Billing setup completed successfully!",
            subscription_id: result.subscription_id,
          });
        } else {
          return json(
            {
              success: false,
              error: result.error || "Failed to create subscription",
            },
            { status: 500 },
          );
        }
      } else {
        return json(
          {
            success: false,
            error: "Billing setup not required or already completed",
          },
          { status: 400 },
        );
      }
    }

    return json({ success: false, error: "Invalid action" }, { status: 400 });
  } catch (error) {
    console.error("Error in billing action:", error);
    return json(
      {
        success: false,
        error:
          error instanceof Error ? error.message : "Unknown error occurred",
      },
      { status: 500 },
    );
  }
};

export default function BillingPage() {
  const { billingData } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const navigation = useNavigation();
  const submit = useSubmit();

  const isLoading = navigation.state === "submitting";
  const isSuccess = actionData?.success;
  const hasError = actionData?.error;

  const handleSetupBilling = () => {
    const formData = new FormData();
    formData.append("action", "setup_billing");
    submit(formData, { method: "post" });
  };

  const handleDismissNotification = () => {
    // In a real app, you might want to store dismissal state in localStorage or database
    console.log("Notification dismissed");
  };

  return (
    <Page>
      <TitleBar title="Billing" />
      <BlockStack gap="500">
        {hasError && (
          <Banner tone="critical">
            <Text as="p">{hasError}</Text>
          </Banner>
        )}

        {isSuccess && (
          <Banner tone="success">
            <InlineStack gap="200" align="start">
              <Icon source={CheckCircleIcon} tone="success" />
              <BlockStack gap="100">
                <Text as="p" variant="bodyMd" fontWeight="medium">
                  🎉 Billing setup completed successfully!
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  Your usage-based billing is now active. You can continue using
                  Better Bundle.
                </Text>
              </BlockStack>
            </InlineStack>
          </Banner>
        )}

        <Layout>
          <Layout.Section>
            {/* Show trial completion notification if needed */}
            <TrialCompletionNotification
              trialStatus={billingData.billing_plan.trial_status}
              billingConfig={billingData.billing_plan.configuration}
              onSetupBilling={handleSetupBilling}
              onDismiss={handleDismissNotification}
              isLoading={isLoading}
            />

            {/* Show billing setup component if trial completed and billing needed */}
            {!billingData.billing_plan.trial_status.is_trial_active &&
              billingData.billing_plan.configuration?.subscription_required &&
              !billingData.billing_plan.configuration?.subscription_id && (
                <BillingSetup
                  billingData={billingData}
                  onSetupBilling={handleSetupBilling}
                  isLoading={isLoading}
                />
              )}

            {/* Show regular billing dashboard if subscription is active or trial is still active */}
            {(billingData.billing_plan.trial_status.is_trial_active ||
              billingData.billing_plan.configuration?.subscription_id) && (
              <BillingDashboard billingData={billingData} />
            )}
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
