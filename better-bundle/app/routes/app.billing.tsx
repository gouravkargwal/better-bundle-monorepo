import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import {
  Page,
  Layout,
  Card,
  BlockStack,
  Text,
  Button,
  Banner,
  ProgressBar,
  InlineStack,
  Badge,
  Icon,
  Spinner,
  Select,
} from "@shopify/polaris";
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  StarFilledIcon,
  ClockIcon,
} from "@shopify/polaris-icons";
import { TitleBar } from "@shopify/app-bridge-react";
import { HeroHeader } from "app/components/UI/HeroHeader";
import { useState } from "react";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: {
        id: true,
        is_active: true,
        currency_code: true,
      },
    });

    if (!shopRecord) {
      throw new Error("Shop not found");
    }

    // Get billing plan
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shopRecord.id,
        status: { in: ["active", "suspended"] },
      },
      orderBy: { created_at: "desc" },
      select: {
        id: true,
        name: true,
        type: true,
        status: true,
        configuration: true,
        effective_from: true,
        effective_to: true,
        is_trial_active: true,
        trial_threshold: true,
        trial_revenue: true,
        trial_usage_records_count: true,
        trial_completed_at: true,
        subscription_id: true,
        subscription_status: true,
        subscription_confirmation_url: true,
        requires_subscription_approval: true,
        created_at: true,
        updated_at: true,
      },
    });

    if (!billingPlan) {
      throw new Error("No billing plan found");
    }

    // Calculate trial status
    const trialRevenue = Number(billingPlan.trial_revenue) || 0;
    const trialThreshold = Number(billingPlan.trial_threshold) || 200;
    const remainingRevenue = Math.max(0, trialThreshold - trialRevenue);
    const trialProgress = Math.min(100, (trialRevenue / trialThreshold) * 100);

    return json({
      shop: shopRecord,
      billingPlan: {
        id: billingPlan.id,
        is_trial_active: billingPlan.is_trial_active,
        trial_revenue: trialRevenue,
        trial_threshold: trialThreshold,
        remaining_revenue: remainingRevenue,
        trial_progress: trialProgress,
        trial_completed_at: billingPlan.trial_completed_at,
        subscription_id: billingPlan.subscription_id,
        subscription_status: billingPlan.subscription_status,
        subscription_confirmation_url:
          billingPlan.subscription_confirmation_url,
        requires_subscription_approval:
          billingPlan.requires_subscription_approval,
        currency: shopRecord.currency_code || "USD",
        usage_count: billingPlan.trial_usage_records_count || 0,
      },
    });
  } catch (error) {
    console.error("Error loading billing data:", error);
    throw new Response("Failed to load billing data", { status: 500 });
  }
};

export default function BillingPage() {
  const { billingPlan } = useLoaderData<typeof loader>();
  const [isLoading, setIsLoading] = useState(false);
  const [spendingLimit, setSpendingLimit] = useState("1000");

  // Add loading state for initial page load
  if (!billingPlan) {
    return (
      <Page>
        <TitleBar title="Billing" />
        <BlockStack gap="300">
          <HeroHeader
            badge="💳 Loading billing information..."
            title="We're gathering your billing details and subscription status"
            subtitle="This may take a moment"
            gradient="gray"
          >
            <div style={{ marginTop: "24px" }}>
              <Spinner size="large" />
            </div>
          </HeroHeader>
        </BlockStack>
      </Page>
    );
  }

  const handleSetupBilling = async () => {
    setIsLoading(true);
    try {
      const response = await fetch("/api/billing/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spendingLimit: parseFloat(spendingLimit) }),
      });

      const result = await response.json();

      if (result.success && result.confirmation_url) {
        // Redirect to Shopify confirmation page
        window.open(result.confirmation_url, "_top");
      } else {
        shopify.toast.show(result.error || "Failed to setup billing", {
          isError: true,
        });
      }
    } catch (error) {
      console.error("Error setting up billing:", error);
      shopify.toast.show("Failed to setup billing", { isError: true });
    } finally {
      setIsLoading(false);
    }
  };

  const formatCurrency = (amount: number, currency: string = "USD") => {
    const symbol = currency === "USD" ? "$" : currency;
    return `${symbol}${amount.toFixed(2)}`;
  };

  // ============= TRIAL ACTIVE =============
  if (billingPlan.is_trial_active) {
    return (
      <Page>
        <TitleBar title="Billing" />
        <BlockStack gap="300">
          <HeroHeader
            badge="🚀 Free Trial Active"
            title="Your Free Trial is Active!"
            subtitle="Use Better Bundle to drive sales and track your progress"
            gradient="blue"
          />

          <Layout>
            <Layout.Section>
              <Card>
                <div style={{ padding: "20px" }}>
                  <BlockStack gap="400">
                    <InlineStack align="space-between">
                      <Text as="h2" variant="headingMd" fontWeight="bold">
                        Trial Progress
                      </Text>
                      <Badge tone="success">Active</Badge>
                    </InlineStack>

                    <div
                      style={{
                        padding: "20px",
                        backgroundColor: "#F0FDF4",
                        borderRadius: "12px",
                        border: "1px solid #22C55E",
                      }}
                    >
                      <BlockStack gap="300">
                        <InlineStack gap="200" align="start">
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              minWidth: "40px",
                              minHeight: "40px",
                              padding: "8px",
                              backgroundColor: "#10B98115",
                              borderRadius: "8px",
                              border: "2px solid #10B98130",
                            }}
                          >
                            <Icon source={StarFilledIcon} tone="success" />
                          </div>
                          <Text as="p" variant="bodyMd">
                            You're currently enjoying your free trial! Use
                            Better Bundle to drive sales.
                          </Text>
                        </InlineStack>
                      </BlockStack>
                    </div>

                    <BlockStack gap="300">
                      <InlineStack align="space-between">
                        <Text as="p" variant="bodyMd" fontWeight="medium">
                          Revenue Progress
                        </Text>
                        <Text as="p" variant="bodyMd" fontWeight="bold">
                          {formatCurrency(
                            billingPlan.trial_revenue,
                            billingPlan.currency,
                          )}{" "}
                          /{" "}
                          {formatCurrency(
                            billingPlan.trial_threshold,
                            billingPlan.currency,
                          )}
                        </Text>
                      </InlineStack>

                      <ProgressBar
                        progress={billingPlan.trial_progress}
                        size="medium"
                      />

                      <Text
                        as="p"
                        variant="bodySm"
                        tone="subdued"
                        alignment="center"
                      >
                        {billingPlan.remaining_revenue > 0
                          ? `${formatCurrency(billingPlan.remaining_revenue, billingPlan.currency)} remaining until trial completion`
                          : "Trial threshold reached - setup billing to continue"}
                      </Text>

                      <div
                        style={{
                          padding: "16px",
                          backgroundColor: "#F8FAFC",
                          borderRadius: "8px",
                          border: "1px solid #E2E8F0",
                          textAlign: "center",
                        }}
                      >
                        <Text as="p" variant="bodySm" tone="subdued">
                          📊 {billingPlan.usage_count} orders tracked
                        </Text>
                      </div>
                    </BlockStack>

                    <div
                      style={{
                        padding: "20px",
                        backgroundColor: "#F0F9FF",
                        borderRadius: "12px",
                        border: "1px solid #BAE6FD",
                      }}
                    >
                      <BlockStack gap="200">
                        <Text as="p" variant="bodyMd" fontWeight="bold">
                          💡 What happens next?
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          When you reach{" "}
                          {formatCurrency(
                            billingPlan.trial_threshold,
                            billingPlan.currency,
                          )}{" "}
                          in attributed revenue, we'll prompt you to set up
                          billing. You'll then pay 3% of attributed revenue,
                          capped at $1,000 per month.
                        </Text>
                      </BlockStack>
                    </div>
                  </BlockStack>
                </div>
              </Card>
            </Layout.Section>
          </Layout>
        </BlockStack>
      </Page>
    );
  }

  // ============= TRIAL COMPLETED - NEEDS SUBSCRIPTION =============
  if (
    !billingPlan.is_trial_active &&
    !billingPlan.subscription_id &&
    billingPlan.trial_completed_at
  ) {
    return (
      <Page>
        <TitleBar title="Billing" />
        <BlockStack gap="300">
          <HeroHeader
            badge="🛑 Trial Completed"
            title="Billing Setup Required"
            subtitle="Your trial has ended. Set up billing to continue using Better Bundle"
            gradient="red"
          />

          <Layout>
            <Layout.Section>
              <Banner tone="critical">
                <BlockStack gap="300">
                  <InlineStack gap="200" align="start">
                    <Icon source={AlertTriangleIcon} tone="critical" />
                    <BlockStack gap="100">
                      <Text as="p" variant="bodyMd" fontWeight="bold">
                        Services Suspended
                      </Text>
                      <Text as="p" variant="bodySm">
                        Your trial has ended. Services are suspended until you
                        set up billing.
                      </Text>
                    </BlockStack>
                  </InlineStack>
                </BlockStack>
              </Banner>
            </Layout.Section>

            <Layout.Section>
              <Card>
                <div style={{ padding: "20px" }}>
                  <BlockStack gap="400">
                    <Text as="h2" variant="headingMd" fontWeight="bold">
                      📊 Trial Summary
                    </Text>

                    <div
                      style={{
                        padding: "20px",
                        backgroundColor: "#FEF3C7",
                        borderRadius: "8px",
                        border: "1px solid #F59E0B",
                      }}
                    >
                      <BlockStack gap="300">
                        <InlineStack align="space-between">
                          <Text as="p" variant="bodyMd">
                            Trial Revenue:
                          </Text>
                          <Text as="p" variant="bodyMd" fontWeight="bold">
                            {formatCurrency(
                              billingPlan.trial_revenue,
                              billingPlan.currency,
                            )}
                          </Text>
                        </InlineStack>

                        <InlineStack align="space-between">
                          <Text as="p" variant="bodyMd">
                            Orders Tracked:
                          </Text>
                          <Text as="p" variant="bodyMd" fontWeight="bold">
                            {billingPlan.usage_count}
                          </Text>
                        </InlineStack>

                        <InlineStack align="space-between">
                          <Text as="p" variant="bodyMd">
                            Completed:
                          </Text>
                          <Text as="p" variant="bodyMd" fontWeight="bold">
                            {new Date(
                              billingPlan.trial_completed_at,
                            ).toLocaleDateString()}
                          </Text>
                        </InlineStack>
                      </BlockStack>
                    </div>

                    <div
                      style={{
                        padding: "20px",
                        backgroundColor: "#F0F9FF",
                        borderRadius: "8px",
                        border: "1px solid #0EA5E9",
                      }}
                    >
                      <BlockStack gap="300">
                        <Text as="p" variant="headingMd" fontWeight="bold">
                          Continue with Usage-Based Billing
                        </Text>

                        <Text as="p" variant="bodyMd">
                          • Pay only 3% of attributed revenue
                        </Text>
                        <Text as="p" variant="bodyMd">
                          • Capped at your selected limit per month (no surprise
                          charges)
                        </Text>
                        <Text as="p" variant="bodyMd">
                          • Cancel anytime
                        </Text>
                        <Text as="p" variant="bodyMd">
                          • Only pay for the value we deliver
                        </Text>
                      </BlockStack>
                    </div>

                    <div
                      style={{
                        padding: "20px",
                        backgroundColor: "#FEFEFE",
                        borderRadius: "8px",
                        border: "1px solid #E5E7EB",
                      }}
                    >
                      <BlockStack gap="300">
                        <Text as="p" variant="headingSm" fontWeight="bold">
                          Select Monthly Spending Limit
                        </Text>

                        <Select
                          label="Monthly spending limit"
                          value={spendingLimit}
                          onChange={setSpendingLimit}
                          options={[
                            { label: "$100 USD", value: "100" },
                            { label: "$250 USD", value: "250" },
                            { label: "$500 USD", value: "500" },
                            { label: "$1,000 USD", value: "1000" },
                            { label: "$2,500 USD", value: "2500" },
                            { label: "$5,000 USD", value: "5000" },
                          ]}
                        />

                        <Text as="p" variant="bodySm" tone="subdued">
                          You can change this limit anytime after setup
                        </Text>
                      </BlockStack>
                    </div>

                    <Button
                      variant="primary"
                      size="large"
                      onClick={handleSetupBilling}
                      loading={isLoading}
                      fullWidth
                    >
                      Setup Billing & Resume Services
                    </Button>

                    <Text
                      as="p"
                      variant="bodySm"
                      tone="subdued"
                      alignment="center"
                    >
                      You'll be redirected to Shopify to approve the billing
                      plan
                    </Text>
                  </BlockStack>
                </div>
              </Card>
            </Layout.Section>
          </Layout>
        </BlockStack>
      </Page>
    );
  }

  // ============= SUBSCRIPTION CANCELLED =============
  if (
    billingPlan.subscription_status === "CANCELLED" ||
    billingPlan.subscription_status === "CANCELLED_BY_MERCHANT"
  ) {
    return (
      <Page>
        <TitleBar title="Billing" />
        <BlockStack gap="300">
          <HeroHeader
            badge="❌ Subscription Cancelled"
            title="Billing Subscription Cancelled"
            subtitle="Your billing subscription has been cancelled. Services are currently paused."
            gradient="red"
          />

          <Layout>
            <Layout.Section>
              <Banner tone="critical">
                <BlockStack gap="300">
                  <InlineStack gap="200" align="start">
                    <Icon source={AlertTriangleIcon} tone="critical" />
                    <BlockStack gap="100">
                      <Text as="p" variant="bodyMd" fontWeight="bold">
                        Services Paused
                      </Text>
                      <Text as="p" variant="bodySm">
                        Your billing subscription has been cancelled. Better
                        Bundle services are currently paused and recommendations
                        are not being shown to your customers.
                      </Text>
                    </BlockStack>
                  </InlineStack>
                </BlockStack>
              </Banner>
            </Layout.Section>

            <Layout.Section>
              <Card>
                <div style={{ padding: "20px" }}>
                  <BlockStack gap="400">
                    <Text as="h2" variant="headingMd" fontWeight="bold">
                      Resume Services
                    </Text>

                    <Text as="p" variant="bodyMd">
                      To resume Better Bundle services, you can set up a new
                      billing subscription:
                    </Text>

                    <div
                      style={{
                        padding: "20px",
                        backgroundColor: "#F0F9FF",
                        borderRadius: "8px",
                        border: "1px solid #0EA5E9",
                      }}
                    >
                      <BlockStack gap="300">
                        <Text as="p" variant="headingSm" fontWeight="bold">
                          Continue with Usage-Based Billing
                        </Text>

                        <Text as="p" variant="bodyMd">
                          • Pay only 3% of attributed revenue
                        </Text>
                        <Text as="p" variant="bodyMd">
                          • Capped at your selected limit per month (no surprise
                          charges)
                        </Text>
                        <Text as="p" variant="bodyMd">
                          • Cancel anytime
                        </Text>
                        <Text as="p" variant="bodyMd">
                          • Only pay for the value we deliver
                        </Text>
                      </BlockStack>
                    </div>

                    <div
                      style={{
                        padding: "20px",
                        backgroundColor: "#FEFEFE",
                        borderRadius: "8px",
                        border: "1px solid #E5E7EB",
                      }}
                    >
                      <BlockStack gap="300">
                        <Text as="p" variant="headingSm" fontWeight="bold">
                          Select Monthly Spending Limit
                        </Text>

                        <Select
                          label="Monthly spending limit"
                          value={spendingLimit}
                          onChange={setSpendingLimit}
                          options={[
                            { label: "$100 USD", value: "100" },
                            { label: "$250 USD", value: "250" },
                            { label: "$500 USD", value: "500" },
                            { label: "$1,000 USD", value: "1000" },
                            { label: "$2,500 USD", value: "2500" },
                            { label: "$5,000 USD", value: "5000" },
                          ]}
                        />

                        <Text as="p" variant="bodySm" tone="subdued">
                          You can change this limit anytime after setup
                        </Text>
                      </BlockStack>
                    </div>

                    <Button
                      variant="primary"
                      size="large"
                      onClick={handleSetupBilling}
                      loading={isLoading}
                      fullWidth
                    >
                      Setup New Billing & Resume Services
                    </Button>

                    <Text
                      as="p"
                      variant="bodySm"
                      tone="subdued"
                      alignment="center"
                    >
                      You'll be redirected to Shopify to approve the new billing
                      plan
                    </Text>
                  </BlockStack>
                </div>
              </Card>
            </Layout.Section>
          </Layout>
        </BlockStack>
      </Page>
    );
  }

  // ============= SUBSCRIPTION PENDING =============
  if (billingPlan.subscription_status === "PENDING") {
    return (
      <Page>
        <TitleBar title="Billing" />
        <BlockStack gap="300">
          <HeroHeader
            badge="⏳ Pending Approval"
            title="Subscription Pending"
            subtitle="Your billing subscription is awaiting approval. Services will resume once approved."
            gradient="orange"
          />

          <Layout>
            <Layout.Section>
              <Banner tone="info">
                <BlockStack gap="300">
                  <InlineStack gap="200" align="start">
                    <Icon source={ClockIcon} tone="info" />
                    <BlockStack gap="100">
                      <Text as="p" variant="bodyMd" fontWeight="bold">
                        Awaiting Approval
                      </Text>
                      <Text as="p" variant="bodySm">
                        Your billing subscription is awaiting approval. Services
                        will resume once approved.
                      </Text>
                    </BlockStack>
                  </InlineStack>
                </BlockStack>
              </Banner>
            </Layout.Section>

            <Layout.Section>
              <Card>
                <div style={{ padding: "20px" }}>
                  <BlockStack gap="400">
                    <div
                      style={{
                        padding: "20px",
                        backgroundColor: "#FEF3C7",
                        borderRadius: "8px",
                        border: "1px solid #F59E0B",
                      }}
                    >
                      <BlockStack gap="300">
                        <InlineStack gap="200" align="start">
                          <Icon source={ClockIcon} tone="warning" />
                          <BlockStack gap="100">
                            <Text as="p" variant="bodyMd" fontWeight="bold">
                              Next Steps
                            </Text>
                            <Text as="p" variant="bodySm">
                              1. Click "Approve Subscription" below
                              <br />
                              2. Complete the approval process in Shopify
                              <br />
                              3. Services will automatically resume
                            </Text>
                          </BlockStack>
                        </InlineStack>
                      </BlockStack>
                    </div>

                    <Text as="h2" variant="headingMd" fontWeight="bold">
                      Approve Your Subscription
                    </Text>

                    <Text as="p" variant="bodyMd">
                      To resume Better Bundle services, please approve your
                      billing subscription:
                    </Text>

                    {billingPlan.subscription_confirmation_url && (
                      <Button
                        variant="primary"
                        size="large"
                        onClick={() =>
                          window.open(
                            billingPlan.subscription_confirmation_url,
                            "_top",
                          )
                        }
                        fullWidth
                      >
                        Approve Subscription in Shopify
                      </Button>
                    )}

                    <InlineStack gap="200" align="center">
                      <Button
                        variant="tertiary"
                        onClick={() => window.location.reload()}
                        loading={isLoading}
                      >
                        Check Status
                      </Button>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Already approved? Click to refresh
                      </Text>
                    </InlineStack>

                    <Text
                      as="p"
                      variant="bodySm"
                      tone="subdued"
                      alignment="center"
                    >
                      Services will automatically resume after approval
                    </Text>
                  </BlockStack>
                </div>
              </Card>
            </Layout.Section>
          </Layout>
        </BlockStack>
      </Page>
    );
  }

  // ============= OTHER SUBSCRIPTION STATUSES =============
  // Handle any other subscription statuses (DECLINED, EXPIRED, etc.)
  return (
    <Page>
      <TitleBar title="Billing" />
      <BlockStack gap="300">
        <HeroHeader
          badge="⚠️ Unknown Status"
          title="Subscription Status Unknown"
          subtitle={`Your subscription status is "${billingPlan.subscription_status}". Please contact support if this persists.`}
          gradient="gray"
        />

        <Layout>
          <Layout.Section>
            <Banner tone="warning">
              <BlockStack gap="300">
                <InlineStack gap="200" align="start">
                  <Icon source={AlertTriangleIcon} tone="warning" />
                  <BlockStack gap="100">
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      Unknown Subscription Status
                    </Text>
                    <Text as="p" variant="bodySm">
                      Your subscription status is "
                      {billingPlan.subscription_status}". This may indicate an
                      issue with your billing setup.
                    </Text>
                  </BlockStack>
                </InlineStack>
              </BlockStack>
            </Banner>
          </Layout.Section>

          <Layout.Section>
            <Card>
              <div style={{ padding: "20px" }}>
                <BlockStack gap="400">
                  <Text as="h2" variant="headingMd" fontWeight="bold">
                    Need Help?
                  </Text>

                  <Text as="p" variant="bodyMd">
                    If you're experiencing issues with your billing
                    subscription, please try:
                  </Text>

                  <div
                    style={{
                      padding: "20px",
                      backgroundColor: "#F0F9FF",
                      borderRadius: "8px",
                      border: "1px solid #0EA5E9",
                    }}
                  >
                    <BlockStack gap="300">
                      <Text as="p" variant="headingSm" fontWeight="bold">
                        Troubleshooting Steps
                      </Text>
                      <Text as="p" variant="bodyMd">
                        • Refresh this page to check for updates
                        <br />
                        • Contact support if the issue persists
                        <br />• Check your Shopify admin for billing
                        notifications
                      </Text>
                    </BlockStack>
                  </div>

                  <InlineStack gap="200" align="center">
                    <Button
                      variant="primary"
                      onClick={() => window.location.reload()}
                      loading={isLoading}
                    >
                      Refresh Page
                    </Button>
                    <Button
                      variant="tertiary"
                      onClick={() =>
                        window.open("mailto:support@betterbundle.com", "_blank")
                      }
                    >
                      Contact Support
                    </Button>
                  </InlineStack>
                </BlockStack>
              </div>
            </Card>
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );

  // ============= SUBSCRIPTION ACTIVE =============
  if (billingPlan.subscription_status === "ACTIVE") {
    return (
      <Page>
        <TitleBar title="Billing" />
        <BlockStack gap="300">
          <HeroHeader
            badge="🎉 Billing Active"
            title="Billing Active"
            subtitle="Your usage-based billing is active. You'll be charged 3% of attributed revenue (capped at $1,000/month)."
            gradient="green"
          />

          <Layout>
            <Layout.Section>
              <Banner tone="success">
                <BlockStack gap="200">
                  <InlineStack gap="200" align="start">
                    <Icon source={CheckCircleIcon} tone="success" />
                    <BlockStack gap="100">
                      <Text as="p" variant="bodyMd" fontWeight="medium">
                        All Systems Active
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Your usage-based billing is active. You'll be charged 3%
                        of attributed revenue (capped at $1,000/month).
                      </Text>
                    </BlockStack>
                  </InlineStack>
                </BlockStack>
              </Banner>
            </Layout.Section>

            <Layout.Section>
              <Card>
                <div style={{ padding: "20px" }}>
                  <BlockStack gap="400">
                    <Text as="h2" variant="headingMd" fontWeight="bold">
                      Current Billing Plan
                    </Text>

                    <div
                      style={{
                        padding: "20px",
                        backgroundColor: "#F0FDF4",
                        borderRadius: "8px",
                        border: "1px solid #22C55E",
                      }}
                    >
                      <BlockStack gap="300">
                        <InlineStack align="space-between">
                          <Text as="p" variant="bodyMd">
                            Plan Type:
                          </Text>
                          <Text as="p" variant="bodyMd" fontWeight="bold">
                            Usage-Based
                          </Text>
                        </InlineStack>

                        <InlineStack align="space-between">
                          <Text as="p" variant="bodyMd">
                            Rate:
                          </Text>
                          <Text as="p" variant="bodyMd" fontWeight="bold">
                            3% of attributed revenue
                          </Text>
                        </InlineStack>

                        <InlineStack align="space-between">
                          <Text as="p" variant="bodyMd">
                            Monthly Cap:
                          </Text>
                          <Text as="p" variant="bodyMd" fontWeight="bold">
                            $1,000
                          </Text>
                        </InlineStack>

                        <InlineStack align="space-between">
                          <Text as="p" variant="bodyMd">
                            Status:
                          </Text>
                          <Badge tone="success">Active</Badge>
                        </InlineStack>
                      </BlockStack>
                    </div>

                    <Text as="p" variant="bodySm" tone="subdued">
                      You can view detailed usage and charges in your Shopify
                      admin under Settings → Billing.
                    </Text>
                  </BlockStack>
                </div>
              </Card>
            </Layout.Section>
          </Layout>
        </BlockStack>
      </Page>
    );
  }

  // ============= FALLBACK =============
  return (
    <Page>
      <TitleBar title="Billing" />
      <BlockStack gap="300">
        <HeroHeader
          badge="💳 Billing Information"
          title="Unable to load billing information"
          subtitle="Please try refreshing the page or contact support if the issue persists"
          gradient="gray"
        />
      </BlockStack>
    </Page>
  );
}
