import type { LoaderFunctionArgs } from "@remix-run/node";
import { redirect } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";
import { useLoaderData } from "@remix-run/react";
import {
  Page,
  Layout,
  Card,
  BlockStack,
  Text,
  Button,
  Badge,
  InlineStack,
  Divider,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { useState, useEffect } from "react";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  // Get the shop
  const shop = await prisma.shop.findUnique({
    where: { shopDomain: session.shop },
    select: { id: true, shopId: true, shopDomain: true },
  });

  if (!shop) {
    return redirect("/app/step/welcome");
  }

  // Check if user has at least started the onboarding process
  // (they should have a shop record, which means they've completed welcome step)
  // This is a basic check - you could add more sophisticated checks if needed

  // Get billing subscription status
  const subscription = await prisma.billingSubscription.findFirst({
    where: { shopId: shop.shopDomain },
    orderBy: { createdAt: "desc" },
  });

  // Get recent charges
  const charges = await prisma.billingCharge.findMany({
    where: { shopId: shop.id },
    orderBy: { createdAt: "desc" },
    take: 10,
  });

  return {
    shop,
    subscription,
    charges,
  };
};

export default function BillingPage() {
  const { shop, subscription, charges } = useLoaderData<typeof loader>();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const createSubscription = async () => {
    setLoading(true);
    setMessage(null);

    try {
      const response = await fetch("/api/billing/manage", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "action=create_subscription",
      });

      const result = await response.json();

      if (result.success) {
        setMessage({
          type: "success",
          text: "Subscription created successfully!",
        });
        // Refresh the page to show updated status
        window.location.reload();
      } else {
        setMessage({
          type: "error",
          text: result.error || "Failed to create subscription",
        });
      }
    } catch (error) {
      setMessage({ type: "error", text: "Network error occurred" });
    } finally {
      setLoading(false);
    }
  };

  const cancelSubscription = async () => {
    if (
      !confirm(
        "Are you sure you want to cancel your subscription? This will stop all billing.",
      )
    ) {
      return;
    }

    setLoading(true);
    setMessage(null);

    try {
      const response = await fetch("/api/billing/manage", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "action=cancel_subscription",
      });

      const result = await response.json();

      if (result.success) {
        setMessage({
          type: "success",
          text: "Subscription cancelled successfully!",
        });
        // Refresh the page to show updated status
        window.location.reload();
      } else {
        setMessage({
          type: "error",
          text: result.error || "Failed to cancel subscription",
        });
      }
    } catch (error) {
      setMessage({ type: "error", text: "Network error occurred" });
    } finally {
      setLoading(false);
    }
  };

  const getSubscriptionStatus = () => {
    if (!subscription) return "No Subscription";

    switch (subscription.status) {
      case "active":
        return "Active";
      case "cancelled":
        return "Cancelled";
      case "declined":
        return "Declined";
      case "frozen":
        return "Frozen";
      default:
        return "Unknown";
    }
  };

  const getStatusTone = () => {
    if (!subscription) return "subdued";

    switch (subscription.status) {
      case "active":
        return "success";
      case "cancelled":
        return "warning";
      case "declined":
        return "critical";
      case "frozen":
        return "attention";
      default:
        return "subdued";
    }
  };

  const isInTrial = () => {
    if (!subscription) return false;
    const now = new Date();
    const trialEnd = new Date(subscription.currentPeriodEnd);
    return now < trialEnd && subscription.status === "active";
  };

  const getTrialDaysLeft = () => {
    if (!isInTrial()) return 0;
    const now = new Date();
    const trialEnd = new Date(subscription.currentPeriodEnd);
    const diffTime = trialEnd.getTime() - now.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return Math.max(0, diffDays);
  };

  return (
    <Page>
      <TitleBar title="Billing & Plans" />
      <Layout>
        {/* Current Plan Status */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">
                Current Plan Status
              </Text>

              <InlineStack align="space-between">
                <Text as="p" variant="bodyMd">
                  <strong>Plan:</strong> Performance-Based Recommendations
                </Text>
                <Badge tone={getStatusTone()}>{getSubscriptionStatus()}</Badge>
              </InlineStack>

              {subscription && (
                <>
                  <InlineStack align="space-between">
                    <Text as="p" variant="bodyMd">
                      <strong>Trial Period:</strong> 14 days
                    </Text>
                    {isInTrial() && (
                      <Badge tone="success">
                        {getTrialDaysLeft()} days left
                      </Badge>
                    )}
                  </InlineStack>

                  <InlineStack align="space-between">
                    <Text as="p" variant="bodyMd">
                      <strong>Next Billing:</strong>{" "}
                      {new Date(
                        subscription.nextBillingDate,
                      ).toLocaleDateString()}
                    </Text>
                  </InlineStack>
                </>
              )}

              {message && (
                <div
                  style={{
                    padding: "12px",
                    borderRadius: "8px",
                    backgroundColor:
                      message.type === "success" ? "#d4edda" : "#f8d7da",
                    color: message.type === "success" ? "#155724" : "#721c24",
                    border: `1px solid ${message.type === "success" ? "#c3e6cb" : "#f5c6cb"}`,
                  }}
                >
                  {message.text}
                </div>
              )}

              <Divider />

              {!subscription ? (
                <BlockStack gap="300">
                  <Text as="p" variant="bodyMd">
                    You don't have an active subscription. Start your 14-day
                    free trial to access all features.
                  </Text>
                  <Button
                    primary
                    onClick={createSubscription}
                    loading={loading}
                    disabled={loading}
                  >
                    Start Free Trial
                  </Button>
                </BlockStack>
              ) : subscription.status === "active" ? (
                <BlockStack gap="300">
                  <Text as="p" variant="bodyMd">
                    Your subscription is active. You can cancel anytime.
                  </Text>
                  <Button
                    variant="outline"
                    onClick={cancelSubscription}
                    loading={loading}
                    disabled={loading}
                  >
                    Cancel Subscription
                  </Button>
                </BlockStack>
              ) : (
                <BlockStack gap="300">
                  <Text as="p" variant="bodyMd">
                    Your subscription is {subscription.status}. You can
                    reactivate anytime.
                  </Text>
                  <Button
                    primary
                    onClick={createSubscription}
                    loading={loading}
                    disabled={loading}
                  >
                    Reactivate Subscription
                  </Button>
                </BlockStack>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Pricing Details */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">
                Pricing Details
              </Text>

              <BlockStack gap="300">
                <InlineStack align="space-between">
                  <Text as="p" variant="bodyMd">
                    <strong>Free Trial:</strong> 14 days
                  </Text>
                  <Badge tone="success">Active</Badge>
                </InlineStack>

                <Text as="p" variant="bodyMd">
                  <strong>Base Commission:</strong> 1.5% of attributed revenue
                </Text>

                <Text as="p" variant="bodyMd">
                  <strong>Performance Bonuses:</strong>
                </Text>
                <BlockStack gap="200">
                  <Text as="p" variant="bodySm" tone="subdued">
                    • Silver (5-10% conversion): +0.5% bonus
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    • Gold (10-15% conversion): +1.0% bonus
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    • Platinum (15%+ conversion): +1.5% bonus
                  </Text>
                </BlockStack>

                <Text as="p" variant="bodyMd">
                  <strong>What's Included:</strong> AI bundle analysis, smart
                  recommendations, conversion tracking, and customer insights
                </Text>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Recent Charges */}
        {charges.length > 0 && (
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Recent Charges
                </Text>

                <BlockStack gap="300">
                  {charges.map((charge) => (
                    <InlineStack key={charge.id} align="space-between">
                      <BlockStack gap="100">
                        <Text as="p" variant="bodyMd">
                          {charge.description}
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          {new Date(charge.createdAt).toLocaleDateString()}
                        </Text>
                      </BlockStack>
                      <BlockStack align="end" gap="100">
                        <Text as="p" variant="bodyMd">
                          ${charge.amount.toFixed(2)} {charge.currency}
                        </Text>
                        <Badge
                          tone={
                            charge.status === "paid" ? "success" : "warning"
                          }
                        >
                          {charge.status}
                        </Badge>
                      </BlockStack>
                    </InlineStack>
                  ))}
                </BlockStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        )}
      </Layout>
    </Page>
  );
}
