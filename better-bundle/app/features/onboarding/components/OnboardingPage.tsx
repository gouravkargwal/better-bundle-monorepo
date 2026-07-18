// features/onboarding/components/OnboardingPage.tsx
import { useNavigation, Form } from "@remix-run/react";
import {
  Page,
  Card,
  Banner,
  BlockStack,
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

const DATA_ITEMS = [
  "Products & collections — to build recommendation groups",
  "Order history — to understand buying patterns",
  "Customer insights — to personalize recommendations",
] as const;

export function OnboardingPage({ data, error }: OnboardingPageProps) {
  const navigation = useNavigation();
  const isLoading = navigation.state === "submitting";

  const plan = data.subscriptionPlan ?? {
    symbol: "$",
    monthly_fee: 29,
    trial_days: 14,
    plan_name: "Pro",
  };

  const hasDiscount = plan.discount_percentage && plan.discount_percentage > 0;

  return (
    <Page>
      <TitleBar title="Get Started" />

      <div
        style={{
          maxWidth: "560px",
          margin: "clamp(16px, 4vh, 48px) auto",
          padding: "0 16px",
        }}
      >
        <BlockStack gap="400">
          <Card>
            <div style={{ padding: "clamp(20px, 3vw, 32px)" }}>
              <BlockStack gap="400">
                {/* What the app does */}
                <div style={{ textAlign: "center" }}>
                  <Text
                    as="h1"
                    variant="headingXl"
                    fontWeight="bold"
                    tone="base"
                  >
                    AI recommendations for your store
                  </Text>
                  <div style={{ marginTop: "8px" }}>
                    <Text as="p" variant="bodyMd" tone="subdued">
                      BetterBundle analyzes your products and orders to show
                      smart recommendations that boost revenue.
                    </Text>
                  </div>
                </div>

                {/* Data transparency */}
                <div
                  style={{
                    padding: "16px",
                    backgroundColor: "rgba(139, 92, 246, 0.04)",
                    borderRadius: "12px",
                    border: "1px solid rgba(139, 92, 246, 0.12)",
                  }}
                >
                  <BlockStack gap="200">
                    <Text
                      as="p"
                      variant="bodySm"
                      fontWeight="semibold"
                      tone="base"
                    >
                      To get started, we'll read your store's:
                    </Text>
                    {DATA_ITEMS.map((item, i) => (
                      <div
                        key={i}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <span style={{ color: "#7C3AED", fontSize: "14px" }}>
                          •
                        </span>
                        <Text as="p" variant="bodySm" tone="subdued">
                          {item}
                        </Text>
                      </div>
                    ))}
                  </BlockStack>
                </div>

                {/* Value proposition */}
                <div
                  style={{
                    padding: "16px",
                    backgroundColor: "rgba(16, 185, 129, 0.06)",
                    borderRadius: "12px",
                    border: "1px solid rgba(16, 185, 129, 0.15)",
                    textAlign: "center",
                  }}
                >
                  <Text
                    as="p"
                    variant="bodyMd"
                    fontWeight="semibold"
                    tone="success"
                  >
                    📈 Boost revenue by up to 30% with AI-powered product
                    recommendations
                  </Text>
                </div>

                {/* Pricing with discount */}
                <div style={{ textAlign: "center" }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "8px",
                      flexWrap: "wrap",
                    }}
                  >
                    {hasDiscount && (
                      <Badge tone="success" size="large">
                        🎉 {(plan.discount_percentage ?? 0) + "% off"}
                      </Badge>
                    )}
                    <Text
                      as="p"
                      variant="headingMd"
                      fontWeight="semibold"
                      tone="base"
                    >
                      {plan.symbol}
                      {plan.monthly_fee}/mo after {plan.trial_days}-day free
                      trial
                    </Text>
                  </div>
                  {hasDiscount && (
                    <div style={{ marginTop: "4px" }}>
                      <Text as="p" variant="bodySm" tone="subdued">
                        <span
                          style={{
                            textDecoration: "line-through",
                            marginRight: "4px",
                          }}
                        >
                          {plan.symbol}
                          {plan.original_monthly_fee}/mo
                        </span>
                        Limited-time launch discount
                      </Text>
                    </div>
                  )}
                  <div style={{ marginTop: "4px" }}>
                    <Text as="p" variant="bodySm" tone="subdued">
                      No credit card required · Set up billing after{" "}
                      {plan.trial_days}-day trial
                    </Text>
                  </div>
                </div>

                {/* CTA */}
                <Form method="post" name="onboarding-form">
                  <Button
                    submit
                    variant="primary"
                    size="large"
                    fullWidth
                    loading={isLoading}
                    disabled={isLoading}
                  >
                    {isLoading
                      ? "Activating..."
                      : `Activate ${plan.trial_days}-Day Free Trial`}
                  </Button>
                </Form>

                <div style={{ textAlign: "center" }}>
                  <Text as="p" variant="bodySm" tone="subdued">
                    ⚡ Setup takes ~2 minutes. You can set up theme extensions
                    while AI analyzes your catalog.
                  </Text>
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
        </BlockStack>
      </div>
    </Page>
  );
}
