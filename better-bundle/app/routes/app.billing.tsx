import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData, useSubmit } from "@remix-run/react";
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
} from "@shopify/polaris";
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  StarFilledIcon,
} from "@shopify/polaris-icons";
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
        suspended_at: true,
        suspension_reason: true,
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
    });

    if (!billingPlan) {
      throw new Error("No billing plan found");
    }

    const config = (billingPlan.configuration as any) || {};

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
  const { shop, billingPlan } = useLoaderData<typeof loader>();
  const submit = useSubmit();
  const [isLoading, setIsLoading] = useState(false);

  const handleSetupBilling = async () => {
    setIsLoading(true);
    try {
      const response = await fetch("/api/billing/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
      <Page title="Billing">
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <InlineStack align="space-between">
                  <Text as="h2" variant="headingMd" fontWeight="bold">
                    🚀 Free Trial Active
                  </Text>
                  <Badge tone="success">Trial Active</Badge>
                </InlineStack>

                <div
                  style={{
                    padding: "20px",
                    backgroundColor: "#F0FDF4",
                    borderRadius: "8px",
                    border: "1px solid #22C55E",
                  }}
                >
                  <BlockStack gap="300">
                    <InlineStack gap="200" align="start">
                      <Icon source={StarFilledIcon} tone="success" />
                      <Text as="p" variant="bodyMd">
                        You're currently enjoying your free trial! Use Better
                        Bundle to drive sales.
                      </Text>
                    </InlineStack>
                  </BlockStack>
                </div>

                <BlockStack gap="300">
                  <InlineStack align="space-between">
                    <Text as="p" variant="bodyMd" fontWeight="medium">
                      Trial Progress
                    </Text>
                    <Text as="p" variant="bodyMd">
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

                  <Text
                    as="p"
                    variant="bodySm"
                    tone="subdued"
                    alignment="center"
                  >
                    📊 {billingPlan.usage_count} orders tracked
                  </Text>
                </BlockStack>

                <div
                  style={{
                    padding: "16px",
                    backgroundColor: "#F8FAFC",
                    borderRadius: "8px",
                    border: "1px solid #E2E8F0",
                  }}
                >
                  <BlockStack gap="200">
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      What happens next?
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      When you reach{" "}
                      {formatCurrency(
                        billingPlan.trial_threshold,
                        billingPlan.currency,
                      )}{" "}
                      in attributed revenue, we'll prompt you to set up billing.
                      You'll then pay 3% of attributed revenue, capped at $1,000
                      per month.
                    </Text>
                  </BlockStack>
                </div>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
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
      <Page title="Billing">
        <Layout>
          <Layout.Section>
            <Banner tone="critical">
              <BlockStack gap="300">
                <InlineStack gap="200" align="start">
                  <Icon source={AlertTriangleIcon} tone="critical" />
                  <BlockStack gap="100">
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      🛑 Trial Completed - Billing Setup Required
                    </Text>
                    <Text as="p" variant="bodySm">
                      Your trial has ended. Services are suspended until you set
                      up billing.
                    </Text>
                  </BlockStack>
                </InlineStack>
              </BlockStack>
            </Banner>
          </Layout.Section>

          <Layout.Section>
            <Card>
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
                      • Capped at $1,000 per month (no surprise charges)
                    </Text>
                    <Text as="p" variant="bodyMd">
                      • Cancel anytime
                    </Text>
                    <Text as="p" variant="bodyMd">
                      • Only pay for the value we deliver
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

                <Text as="p" variant="bodySm" tone="subdued" alignment="center">
                  You'll be redirected to Shopify to approve the billing plan
                </Text>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  // ============= SUBSCRIPTION PENDING =============
  if (billingPlan.subscription_status === "PENDING") {
    return (
      <Page title="Billing">
        <Layout>
          <Layout.Section>
            <Banner tone="info">
              <BlockStack gap="300">
                <InlineStack gap="200" align="start">
                  <Icon source={StarFilledIcon} tone="info" />
                  <BlockStack gap="100">
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      ⏳ Subscription Pending Approval
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
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd" fontWeight="bold">
                  Waiting for Approval
                </Text>

                <Text as="p" variant="bodyMd">
                  If you haven't approved the subscription yet, please click the
                  button below:
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

                <Text as="p" variant="bodySm" tone="subdued" alignment="center">
                  Services will automatically resume after approval
                </Text>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  // ============= SUBSCRIPTION ACTIVE =============
  if (billingPlan.subscription_status === "ACTIVE") {
    return (
      <Page title="Billing">
        <Layout>
          <Layout.Section>
            <Banner tone="success">
              <BlockStack gap="200">
                <InlineStack gap="200" align="start">
                  <Icon source={CheckCircleIcon} tone="success" />
                  <BlockStack gap="100">
                    <Text as="p" variant="bodyMd" fontWeight="medium">
                      🎉 Billing Active
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
                  You can view detailed usage and charges in your Shopify admin
                  under Settings → Billing.
                </Text>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  // ============= FALLBACK =============
  return (
    <Page title="Billing">
      <Layout>
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">
                Billing Information
              </Text>
              <Text as="p" variant="bodyMd">
                Loading billing information...
              </Text>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
