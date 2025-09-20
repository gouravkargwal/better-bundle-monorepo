import type { LoaderFunctionArgs, ActionFunctionArgs } from "@remix-run/node";
import { useActionData, Form, json } from "@remix-run/react";
import {
  Page,
  Card,
  Button,
  BlockStack,
  Text,
  Banner,
  InlineStack,
  Icon,
  Badge,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import {
  StarFilledIcon,
  CashDollarIcon,
  EyeCheckMarkIcon,
  TeamIcon,
  CheckIcon,
  ArrowRightIcon,
} from "@shopify/polaris-icons";
import polarisStyles from "@shopify/polaris/build/esm/styles.css?url";

import { authenticate } from "../shopify.server";
import prisma from "app/db.server";
import {
  activateAtlasWebPixel,
  activateTrialBillingPlan,
  createShopAndSetOnboardingCompleted,
  getShopInfoFromShopify,
  getShopOnboardingCompleted,
  markOnboardingCompleted,
} from "app/services/shop.service";
import { triggerFullAnalysis } from "app/services/analysis.service";

export const links = () => [{ rel: "stylesheet", href: polarisStyles }];

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, redirect } = await authenticate.admin(request);
  console.log("session", session, "In onboarding route");
  const onboardingCompleted = await getShopOnboardingCompleted(session.shop);
  console.log(
    "🔍 Onboarding route - onboarding completed:",
    onboardingCompleted,
  );
  if (onboardingCompleted) {
    console.log("✅ Onboarding already completed, redirecting to app");
    throw redirect("/app");
  }
  console.log("📝 Onboarding not completed, staying on onboarding page");
  return null;
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session, admin, redirect } = await authenticate.admin(request);

  try {
    const shopData = await getShopInfoFromShopify(admin);
    // Use atomic transaction to ensure all database operations succeed or fail together
    await prisma.$transaction(async (tx) => {
      // Step 1: Create/update shop record (idempotent)
      const shop = await createShopAndSetOnboardingCompleted(
        session,
        shopData,
        tx,
      );

      // Step 2: Create/update billing plan (idempotent) - using shop.id from the transaction
      await activateTrialBillingPlan(session.shop, shop, tx);

      // Step 3: Mark onboarding as completed (atomic with other operations)
      await markOnboardingCompleted(session.shop, tx);
    });

    // Step 4: Activate web pixel (critical for tracking)
    try {
      await activateAtlasWebPixel(admin, session.shop);
    } catch (error) {
      console.error("Web pixel activation failed:", error);
      throw new Error("Failed to activate web pixel. Please try again.");
    }

    // Step 5: Trigger analysis (critical for functionality)
    try {
      await triggerFullAnalysis(session.shop);
    } catch (error) {
      console.error("Analysis trigger failed:", error);
      throw new Error("Failed to start analysis. Please try again.");
    }

    return redirect("/app");
  } catch (error) {
    console.error("Failed to complete onboarding:", error);
    return json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Failed to complete onboarding. Please try again.",
      },
      { status: 500 },
    );
  }
};

export default function OnboardingPage() {
  const actionData = useActionData<typeof action>();

  const features = [
    {
      icon: CashDollarIcon,
      title: "Increase Revenue",
      description: "Boost sales with AI-powered product recommendations",
      color: "#10B981",
      badge: "Up to 30% more sales",
    },
    {
      icon: EyeCheckMarkIcon,
      title: "Smart Analytics",
      description: "Track performance with detailed attribution metrics",
      color: "#3B82F6",
      badge: "Real-time insights",
    },
    {
      icon: TeamIcon,
      title: "Better Experience",
      description: "Personalized shopping for your customers",
      color: "#8B5CF6",
      badge: "Higher engagement",
    },
    {
      icon: StarFilledIcon,
      title: "Easy Setup",
      description: "Get started in minutes with our simple setup",
      color: "#F59E0B",
      badge: "No coding required",
    },
  ];

  const benefits = [
    "AI-powered product recommendations",
    "Real-time performance analytics",
    "Revenue attribution tracking",
    "Customer behavior insights",
    "Easy-to-use dashboard",
    "24/7 automated optimization",
  ];

  return (
    <Page>
      <TitleBar title="Welcome to BetterBundle!" />

      <BlockStack gap="600">
        {/* Hero Section */}
        <div
          style={{
            padding: "48px 32px",
            background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            borderRadius: "20px",
            color: "white",
            textAlign: "center",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div style={{ position: "relative", zIndex: 2 }}>
            <Text as="h1" variant="heading2xl" fontWeight="bold">
              🚀 Welcome to BetterBundle!
            </Text>
            <div style={{ marginTop: "16px" }}>
              <Text as="p" variant="headingMd" tone="subdued">
                Transform your store with AI-powered product recommendations
              </Text>
            </div>
            <div style={{ marginTop: "24px" }}>
              <Badge size="large" tone="info">
                Start earning more revenue in minutes
              </Badge>
            </div>
          </div>

          {/* Decorative elements */}
          <div
            style={{
              position: "absolute",
              top: "-50px",
              right: "-50px",
              width: "200px",
              height: "200px",
              background: "rgba(255,255,255,0.1)",
              borderRadius: "50%",
              zIndex: 1,
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: "-30px",
              left: "-30px",
              width: "150px",
              height: "150px",
              background: "rgba(255,255,255,0.05)",
              borderRadius: "50%",
              zIndex: 1,
            }}
          />
        </div>

        {/* Features Grid */}
        <BlockStack gap="400">
          <div style={{ textAlign: "center" }}>
            <Text as="h2" variant="headingLg" fontWeight="bold">
              Why Choose BetterBundle?
            </Text>
            <div style={{ marginTop: "8px" }}>
              <Text as="p" variant="bodyLg" tone="subdued">
                Everything you need to boost your store's performance
              </Text>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: "20px",
              alignItems: "stretch",
            }}
          >
            {features.map((feature, index) => (
              <div
                key={index}
                style={{
                  transition: "all 0.3s ease-in-out",
                  cursor: "pointer",
                  borderRadius: "16px",
                  overflow: "hidden",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = "translateY(-8px)";
                  e.currentTarget.style.boxShadow =
                    "0 20px 40px rgba(0,0,0,0.1)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "translateY(0)";
                  e.currentTarget.style.boxShadow = "none";
                }}
              >
                <Card>
                  <div style={{ padding: "24px" }}>
                    <BlockStack gap="300">
                      <InlineStack align="space-between" blockAlign="center">
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            width: "48px",
                            height: "48px",
                            backgroundColor: feature.color + "15",
                            borderRadius: "16px",
                            border: `2px solid ${feature.color}30`,
                          }}
                        >
                          <Icon source={feature.icon} tone="base" />
                        </div>
                        <Badge tone="info" size="small">
                          {feature.badge}
                        </Badge>
                      </InlineStack>

                      <BlockStack gap="200">
                        <Text as="h3" variant="headingMd" fontWeight="bold">
                          {feature.title}
                        </Text>
                        <Text as="p" variant="bodyMd" tone="subdued">
                          {feature.description}
                        </Text>
                      </BlockStack>
                    </BlockStack>
                  </div>
                </Card>
              </div>
            ))}
          </div>
        </BlockStack>

        {/* Benefits Section */}
        <div
          style={{
            padding: "32px",
            backgroundColor: "#F8FAFC",
            borderRadius: "16px",
            border: "1px solid #E2E8F0",
          }}
        >
          <BlockStack gap="400">
            <div style={{ textAlign: "center" }}>
              <Text as="h3" variant="headingLg" fontWeight="bold">
                What You'll Get
              </Text>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
                gap: "16px",
              }}
            >
              {benefits.map((benefit, index) => (
                <InlineStack key={index} gap="200" blockAlign="center">
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: "24px",
                      height: "24px",
                      backgroundColor: "#10B981",
                      borderRadius: "50%",
                      flexShrink: 0,
                    }}
                  >
                    <Icon source={CheckIcon} tone="base" />
                  </div>
                  <Text as="p" variant="bodyMd">
                    {benefit}
                  </Text>
                </InlineStack>
              ))}
            </div>
          </BlockStack>
        </div>

        {/* Setup Section */}
        <Card>
          <div style={{ padding: "32px" }}>
            <BlockStack gap="400">
              <div style={{ textAlign: "center" }}>
                <Text as="h3" variant="headingLg" fontWeight="bold">
                  Ready to Get Started?
                </Text>
                <div style={{ marginTop: "8px" }}>
                  <Text as="p" variant="bodyLg" tone="subdued">
                    Complete your setup and start earning more revenue today
                  </Text>
                </div>
              </div>

              {actionData?.error && (
                <Banner tone="critical">
                  <Text as="p">{actionData.error}</Text>
                </Banner>
              )}

              <div style={{ textAlign: "center" }}>
                <Form method="post">
                  <Button
                    submit
                    variant="primary"
                    size="large"
                    icon={ArrowRightIcon}
                    loading={false}
                  >
                    Complete Setup & Start Earning
                  </Button>
                </Form>
              </div>

              <div style={{ textAlign: "center" }}>
                <Text as="p" variant="bodySm" tone="subdued">
                  Setup takes less than 2 minutes • No coding required
                </Text>
              </div>
            </BlockStack>
          </div>
        </Card>
      </BlockStack>
    </Page>
  );
}
