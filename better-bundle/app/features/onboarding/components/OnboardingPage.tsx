// features/onboarding/components/OnboardingPage.tsx
import { useNavigation, Form } from "@remix-run/react";
import {
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
import { HeroHeader } from "../../../components/UI/HeroHeader";
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
    cap_amount: 299,
    trial_revenue_threshold: 1000,
    plan_name: "Pay As You Go",
  };

  const ratePercent = (plan.commission_rate * 100)
    .toFixed(1)
    .replace(/\.0$/, "");

  return (
    <Page>
      <TitleBar title="Get Started" />
      <BlockStack gap="300">
        <HeroHeader
          title="Turn your store's data into smarter recommendations"
          subtitle="BetterBundle analyzes your products, orders, and shoppers — then starts showing smart offers across your storefront in minutes."
          variant="gradient"
          align="left"
        />

        <BlockStack gap="400">
          {/* How it works */}
          <Card>
            <div style={{ padding: "24px" }}>
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
                    <div
                      key={step.title}
                      style={{
                        padding: "16px",
                        backgroundColor: "#EFF6FF",
                        borderRadius: "12px",
                        border: "1px solid #BFDBFE",
                      }}
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
                    </div>
                  ))}
                </div>
              </BlockStack>
            </div>
          </Card>

          {/* Data transparency */}
          <Card>
            <div style={{ padding: "24px" }}>
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
                    <div
                      key={item.label}
                      style={{
                        padding: "16px",
                        backgroundColor: "#F5F3FF",
                        borderRadius: "12px",
                        border: "1px solid #DDD6FE",
                      }}
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
                    </div>
                  ))}
                </div>
              </BlockStack>
            </div>
          </Card>

          {/* Pricing */}
          <Card>
            <div style={{ padding: "24px" }}>
              <BlockStack gap="400">
                <InlineStackHeader
                  title="💳 Simple pricing"
                  subtitle="You only pay when we generate revenue for you — nothing upfront."
                  badge={<Badge tone="success" size="large">No monthly fee</Badge>}
                />

                <div
                  style={{
                    padding: "24px",
                    backgroundColor: "#F0FDF4",
                    borderRadius: "12px",
                    border: "2px solid #22C55E",
                    textAlign: "center",
                  }}
                >
                  <BlockStack gap="100">
                    <Text as="h3" variant="heading2xl" fontWeight="bold">
                      {ratePercent}% of the revenue we generate
                    </Text>
                    <Text as="p" variant="bodyMd" tone="subdued">
                      Free until we&apos;ve driven {plan.symbol}
                      {plan.trial_revenue_threshold.toLocaleString()} in sales
                    </Text>
                  </BlockStack>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "repeat(auto-fit, minmax(240px, 1fr))",
                    gap: "12px",
                  }}
                >
                  <div
                    style={{
                      padding: "16px",
                      backgroundColor: "#FEF3C7",
                      borderRadius: "12px",
                      border: "1px solid #FCD34D",
                    }}
                  >
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
                  </div>
                  <div
                    style={{
                      padding: "16px",
                      backgroundColor: "#EFF6FF",
                      borderRadius: "12px",
                      border: "1px solid #BFDBFE",
                    }}
                  >
                    <BlockStack gap="100">
                      <Text as="p" variant="bodyMd" fontWeight="semibold">
                        💳 No credit card required
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        You approve the charge in Shopify before anything is
                        billed.
                      </Text>
                    </BlockStack>
                  </div>
                </div>
              </BlockStack>
            </div>
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
          <div
            style={{
              background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
              borderRadius: "16px",
              padding: "32px 24px",
              textAlign: "center",
              boxShadow:
                "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              position: "relative",
              overflow: "hidden",
            }}
          >
            <BlockStack gap="200" inlineAlign="center">
              <Text
                as="h3"
                variant="headingLg"
                fontWeight="bold"
                tone="text-inverse"
              >
                Ready to boost your revenue?
              </Text>
              <Text as="p" variant="bodyMd" tone="text-inverse-secondary">
                Start free — no credit card required. Your recommendations can
                be live in minutes.
              </Text>
              <div style={{ marginTop: "12px" }}>
                <Form method="post" name="onboarding-form">
                  <Button
                    submit
                    variant="primary"
                    size="large"
                    loading={isLoading}
                    disabled={isLoading}
                  >
                    {isLoading ? "Activating..." : "Start Free"}
                  </Button>
                </Form>
              </div>
              <Text as="p" variant="bodySm" tone="text-inverse-secondary">
                ⚡ Setup takes ~2 minutes. You can set up theme extensions while
                AI analyzes your catalog.
              </Text>
            </BlockStack>
          </div>
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