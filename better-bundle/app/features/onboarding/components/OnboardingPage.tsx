// features/onboarding/components/OnboardingPage.tsx
import { useNavigation, Form } from "@remix-run/react";
import {
  Box,
  Page,
  Card,
  Banner,
  BlockStack,
  InlineStack,
  Text,
  Button,
  Badge,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import type {
  OnboardingData,
  OnboardingError,
} from "../services/onboarding.types";
import { MIN_TRIAL_ORDERS } from "../../billing/trialGate";

interface OnboardingPageProps {
  data: OnboardingData;
  error?: OnboardingError;
}

const STEPS = [
  {
    icon: "🛍️",
    title: "Connect your store",
    description:
      "Approve the app and grant read access to your products and orders.",
  },
  {
    icon: "🤖",
    title: "AI analyzes your catalog",
    description:
      "We build a recommendation map from your products, order history, and customer behavior.",
  },
  {
    icon: "📈",
    title: "Recommendations go live",
    description:
      "Smart offers start appearing on your product pages, post-purchase, and the thank-you page — plus checkout if you're on Shopify Plus.",
  },
] as const;

const DATA_ITEMS = [
  {
    icon: "🗂️",
    label: "Products & collections",
    detail: "to build recommendation groups",
  },
  {
    icon: "📦",
    label: "Order history",
    detail: "to understand buying patterns",
  },
  {
    icon: "👥",
    label: "Customer insights",
    detail: "to personalize recommendations",
  },
] as const;

export function OnboardingPage({ data, error }: OnboardingPageProps) {
  const navigation = useNavigation();
  const isLoading = navigation.state === "submitting";

  const plan = data.subscriptionPlan ?? {
    currency_code: "USD",
    commission_rate: 0.03,
    cap_amount: 29,
    trial_revenue_threshold: 1000,
    plan_name: "Pay As You Go",
  };

  const ratePercent = (plan.commission_rate * 100)
    .toFixed(1)
    .replace(/\.0$/, "");

  return (
    <Page
      title="Get started"
      subtitle="We'll analyse your products and orders, then start showing recommendations across your store."
    >
      <TitleBar title="Get Started" />
      <BlockStack gap="300">

        <BlockStack gap="400">
          {/* How it works */}
          <Card>
            <BlockStack gap="400">
              <InlineStackHeader
                title="⚡ How it works"
                subtitle="Setup takes about 2 minutes — most of it happens automatically."
                badge={<Badge tone="info" size="large">~2 min setup</Badge>}
              />
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "repeat(auto-fit, minmax(220px, 1fr))",
                  gap: "12px",
                }}
              >
                {STEPS.map((step, i) => (
                  <Box
                    key={step.title}
                    padding="400"
                    background="bg-surface-info"
                    borderRadius="300"
                  >
                    <BlockStack gap="200">
                      <InlineStack gap="200" blockAlign="center">
                        <span style={{ fontSize: "20px" }}>{step.icon}</span>
                        <Text as="p" variant="bodySm" tone="subdued">
                          Step {i + 1}
                        </Text>
                      </InlineStack>
                      <Text as="p" variant="bodyMd" fontWeight="semibold">
                        {step.title}
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {step.description}
                      </Text>
                    </BlockStack>
                  </Box>
                ))}
              </div>
            </BlockStack>

          </Card>

          {/* Data transparency */}
          <Card>
            <BlockStack gap="400">
              <InlineStackHeader
                title="🔒 What we read from your store"
                subtitle="Only what's needed to build smart recommendations — nothing else."
                badge={<Badge tone="success" size="large">Read-only</Badge>}
              />
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "repeat(auto-fit, minmax(220px, 1fr))",
                  gap: "12px",
                }}
              >
                {DATA_ITEMS.map((item) => (
                  <Box
                    key={item.label}
                    padding="400"
                    background="bg-surface-secondary"
                    borderRadius="300"
                  >
                    <BlockStack gap="100">
                      <InlineStack gap="200" blockAlign="center">
                        <span style={{ fontSize: "18px" }}>{item.icon}</span>
                        <Text as="p" variant="bodyMd" fontWeight="semibold">
                          {item.label}
                        </Text>
                      </InlineStack>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {item.detail}
                      </Text>
                    </BlockStack>
                  </Box>
                ))}
              </div>
            </BlockStack>

          </Card>

          {/* Pricing */}
          <Card>
            <BlockStack gap="400">
              <InlineStackHeader
                title="💳 Simple pricing"
                subtitle="You only pay on sales our recommendations are part of — nothing upfront."
                badge={<Badge tone="success" size="large">No monthly fee</Badge>}
              />

              <Box padding="500" background="bg-surface-success" borderRadius="300">
                <BlockStack gap="100">
                  <Text as="h3" variant="heading2xl" fontWeight="bold">
                    {ratePercent}% of attributed revenue
                  </Text>
                  <Text as="p" variant="bodyMd" tone="subdued">
                    Free until we&apos;ve driven{" "}
                    {new Intl.NumberFormat("en-US", {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    }).format(plan.trial_revenue_threshold)} {plan.currency_code}{" "}
                    in sales
                  </Text>
                </BlockStack>
              </Box>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "repeat(auto-fit, minmax(240px, 1fr))",
                  gap: "12px",
                }}
              >
                <Box padding="400" background="bg-surface-warning" borderRadius="300">
                  <BlockStack gap="100">
                    <Text as="p" variant="bodyMd" fontWeight="semibold">
                      🎯 You set the limit
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      When the free period ends you choose a monthly limit —{" "}
                      {new Intl.NumberFormat("en-US", {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      }).format(plan.cap_amount)} {plan.currency_code}{" "}
                      to start — and we can
                      never charge above it. Change it whenever you like.
                    </Text>
                  </BlockStack>
                </Box>
                <Box padding="400" background="bg-surface-info" borderRadius="300">
                  <BlockStack gap="100">
                    <Text as="p" variant="bodyMd" fontWeight="semibold">
                      💳 No credit card required
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      You approve the charge in Shopify before anything is
                      billed.
                    </Text>
                  </BlockStack>
                </Box>
              </div>
            </BlockStack>

          </Card>

          {error && (
            <Banner tone="critical">
              <Text as="p" variant="bodyMd" tone="critical">
                {error.error}
              </Text>
              <div style={{ marginTop: "4px" }}>
                <Text as="p" variant="bodySm" tone="subdued">
                  Please try again or contact support if the issue persists.
                </Text>
              </div>
            </Banner>
          )}

          {/* CTA */}
          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">
                Ready to start?
              </Text>
              <Text as="p" tone="subdued">
                No credit card required. You pay nothing until recommendations
                have earned you{" "}
                {new Intl.NumberFormat("en-US", {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                }).format(plan.trial_revenue_threshold)} {plan.currency_code}{" "}
                across{" "}
                {MIN_TRIAL_ORDERS} separate orders — enough that you can see
                it working before you decide. Setup takes about two minutes.
              </Text>
              <Form method="post" name="onboarding-form">
                <Button
                  submit
                  variant="primary"
                  size="large"
                  loading={isLoading}
                  disabled={isLoading}
                >
                  {isLoading ? "Setting up…" : "Start free"}
                </Button>
              </Form>
            </BlockStack>
          </Card>
        </BlockStack>
      </BlockStack>
    </Page>
  );
}

function InlineStackHeader({
  title,
  subtitle,
  badge,
}: {
  title: string;
  subtitle: string;
  badge: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "16px",
        flexWrap: "wrap",
      }}
    >
      <div style={{ minWidth: 0 }}>
        <Text variant="headingMd" as="h3">
          {title}
        </Text>
        <div style={{ marginTop: "4px" }}>
          <Text as="p" tone="subdued">
            {subtitle}
          </Text>
        </div>
      </div>
      {badge}
    </div>
  );
}