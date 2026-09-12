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
      "Smart offers start appearing across storefront, checkout, and post-purchase.",
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
    symbol: "$",
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
                subtitle="You only pay when we generate revenue for you — nothing upfront."
                badge={<Badge tone="success" size="large">No monthly fee</Badge>}
              />

              <Box padding="500" background="bg-surface-success" borderRadius="300">
                <BlockStack gap="100">
                  <Text as="h3" variant="heading2xl" fontWeight="bold">
                    {ratePercent}% of the revenue we generate
                  </Text>
                  <Text as="p" variant="bodyMd" tone="subdued">
                    Free until we&apos;ve driven {plan.symbol}
                    {plan.trial_revenue_threshold.toLocaleString()} in sales
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
                      🎯 Always capped
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Never more than {plan.symbol}
                      {plan.cap_amount.toLocaleString()} in 30 days — no
                      surprise charges.
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
                No credit card required, and nothing to pay until
                recommendations have earned you your first $1,000. Setup takes
                about two minutes — you can add placements to your theme while
                we analyse your catalogue.
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