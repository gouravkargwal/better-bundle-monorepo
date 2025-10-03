import type { LoaderFunctionArgs, ActionFunctionArgs } from "@remix-run/node";
import { useActionData, Form, json, useNavigation } from "@remix-run/react";
import {
  Page,
  Card,
  Button,
  BlockStack,
  Text,
  Banner,
  Badge,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { ArrowRightIcon } from "@shopify/polaris-icons";
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
import FeatureCard from "app/components/Onboarding/FeatureCard";
import { Benefits } from "app/components/Onboarding/Benefits";

export const links = () => [{ rel: "stylesheet", href: polarisStyles }];

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, redirect } = await authenticate.admin(request);
  const onboardingCompleted = await getShopOnboardingCompleted(session.shop);

  if (onboardingCompleted) {
    throw redirect("/app");
  }
  return null;
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session, admin, redirect } = await authenticate.admin(request);
  try {
    const shopData = await getShopInfoFromShopify(admin);
    await prisma.$transaction(async (tx) => {
      const shop = await createShopAndSetOnboardingCompleted(
        session,
        shopData,
        tx,
      );

      await activateTrialBillingPlan(session.shop, shop, tx);

      await markOnboardingCompleted(session.shop, tx);
    });

    // Step 4: Activate web pixel (critical for tracking)
    try {
      await activateAtlasWebPixel(admin, session.shop);
    } catch (error) {
      console.error("❌ Web pixel activation failed:", error);
      throw new Error("Failed to activate web pixel. Please try again.");
    }

    // Step 5: Trigger analysis (critical for functionality)
    try {
      await triggerFullAnalysis(session.shop);
    } catch (error) {
      console.error("❌ Analysis trigger failed:", error);
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
  const navigation = useNavigation();
  const isLoading =
    ["loading", "submitting"].includes(navigation.state) &&
    navigation.formMethod === "POST";
  return (
    <Page>
      <TitleBar title="Welcome to BetterBundle!" />

      <BlockStack gap="600">
        <div
          style={{
            padding: "40px 32px",
            background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            borderRadius: "24px",
            color: "white",
            textAlign: "center",
            position: "relative",
            overflow: "hidden",
            boxShadow:
              "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
          }}
        >
          <div style={{ position: "relative", zIndex: 2 }}>
            {/* Hero Badge */}
            <div style={{ marginBottom: "16px" }}>
              <Badge
                size="large"
                tone="info"
                style={{
                  backgroundColor: "rgba(255, 255, 255, 0.2)",
                  border: "1px solid rgba(255, 255, 255, 0.3)",
                  color: "white",
                  fontWeight: "600",
                }}
              >
                ✨ New AI-Powered Solution
              </Badge>
            </div>

            {/* Main Headline */}
            <Text
              as="h1"
              variant="heading2xl"
              fontWeight="bold"
              style={{
                fontSize: "3rem",
                lineHeight: "1.1",
                marginBottom: "16px",
                background: "linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              Welcome to BetterBundle!
            </Text>

            {/* Subheadline */}
            <div
              style={{
                marginBottom: "20px",
                maxWidth: "600px",
                margin: "0 auto 20px",
              }}
            >
              <Text
                as="p"
                variant="headingLg"
                style={{
                  color: "rgba(255,255,255,0.95)",
                  lineHeight: "1.6",
                  fontWeight: "500",
                }}
              >
                Transform your store with AI-powered product recommendations
                that boost revenue by up to 30%
              </Text>
            </div>

            {/* Key Benefits Row */}
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                gap: "24px",
                marginBottom: "24px",
                flexWrap: "wrap",
              }}
            >
              <div
                style={{ display: "flex", alignItems: "center", gap: "8px" }}
              >
                <div
                  style={{
                    width: "8px",
                    height: "8px",
                    backgroundColor: "#10B981",
                    borderRadius: "50%",
                  }}
                />
                <Text
                  as="span"
                  variant="bodyLg"
                  style={{ color: "rgba(255,255,255,0.9)" }}
                >
                  $200 Free Credits
                </Text>
              </div>
              <div
                style={{ display: "flex", alignItems: "center", gap: "8px" }}
              >
                <div
                  style={{
                    width: "8px",
                    height: "8px",
                    backgroundColor: "#10B981",
                    borderRadius: "50%",
                  }}
                />
                <Text
                  as="span"
                  variant="bodyLg"
                  style={{ color: "rgba(255,255,255,0.9)" }}
                >
                  No Setup Fees
                </Text>
              </div>
              <div
                style={{ display: "flex", alignItems: "center", gap: "8px" }}
              >
                <div
                  style={{
                    width: "8px",
                    height: "8px",
                    backgroundColor: "#10B981",
                    borderRadius: "50%",
                  }}
                />
                <Text
                  as="span"
                  variant="bodyLg"
                  style={{ color: "rgba(255,255,255,0.9)" }}
                >
                  2-Minute Setup
                </Text>
              </div>
            </div>

            {/* Pay-As-Performance Highlight */}
            <div
              style={{
                marginBottom: "24px",
                padding: "20px",
                backgroundColor: "rgba(255,255,255,0.12)",
                borderRadius: "16px",
                border: "1px solid rgba(255,255,255,0.2)",
                backdropFilter: "blur(10px)",
                maxWidth: "500px",
                margin: "0 auto 24px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "12px",
                  marginBottom: "16px",
                }}
              >
                <div
                  style={{
                    width: "32px",
                    height: "32px",
                    backgroundColor: "rgba(16, 185, 129, 0.2)",
                    borderRadius: "8px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Text as="span" variant="bodyLg" fontWeight="bold">
                    💳
                  </Text>
                </div>
                <Text as="h3" variant="headingLg" fontWeight="bold">
                  Pay-As-Performance Model
                </Text>
              </div>

              <Text
                as="p"
                variant="bodyLg"
                style={{
                  color: "rgba(255,255,255,0.95)",
                  lineHeight: "1.5",
                  marginBottom: "20px",
                }}
              >
                Only pay when you see results • No upfront costs • Risk-free
                trial
              </Text>

              <Badge
                size="large"
                tone="success"
                style={{
                  backgroundColor: "rgba(16, 185, 129, 0.2)",
                  border: "1px solid rgba(16, 185, 129, 0.3)",
                  color: "#10B981",
                  fontWeight: "600",
                }}
              >
                🎯 Guaranteed Results
              </Badge>
            </div>

            {/* Call to Action Button */}
            <div>
              <Form method="post" name="onboarding-form">
                <Button
                  submit
                  variant="primary"
                  size="large"
                  icon={isLoading ? undefined : ArrowRightIcon}
                  loading={isLoading}
                  disabled={isLoading}
                  style={{
                    padding: "16px 32px",
                    fontSize: "18px",
                    fontWeight: "600",
                    borderRadius: "12px",
                    boxShadow: "0 4px 14px 0 rgba(0, 118, 255, 0.39)",
                    border: "none",
                  }}
                >
                  {isLoading
                    ? "Setting up your store..."
                    : "Start Your Free Trial Now"}
                </Button>
              </Form>
              <div style={{ marginTop: "12px" }}>
                <Text
                  as="p"
                  variant="bodyMd"
                  style={{
                    color: "rgba(255,255,255,0.8)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "16px",
                    flexWrap: "wrap",
                  }}
                >
                  <span>⚡ Setup in 2 minutes</span>
                  <span>•</span>
                  <span>🔒 No coding required</span>
                  <span>•</span>
                  <span>📈 Results in 24 hours</span>
                </Text>
              </div>
            </div>
          </div>

          {/* Enhanced Decorative elements */}
          <div
            style={{
              position: "absolute",
              top: "-100px",
              right: "-100px",
              width: "300px",
              height: "300px",
              background:
                "radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)",
              borderRadius: "50%",
              zIndex: 1,
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: "-80px",
              left: "-80px",
              width: "250px",
              height: "250px",
              background:
                "radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 70%)",
              borderRadius: "50%",
              zIndex: 1,
            }}
          />
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "-50px",
              width: "100px",
              height: "100px",
              background: "rgba(255,255,255,0.03)",
              borderRadius: "50%",
              zIndex: 1,
            }}
          />
        </div>
        <FeatureCard />
        <Benefits />

        {/* Error Display Section */}
        {actionData?.error && (
          <Card>
            <div style={{ padding: "24px" }}>
              <Banner tone="critical">
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "12px",
                    padding: "20px",
                    backgroundColor: "#FEF2F2",
                    border: "1px solid #FECACA",
                    borderRadius: "12px",
                    boxShadow:
                      "0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)",
                  }}
                >
                  {/* Error Icon */}
                  <div
                    style={{
                      flexShrink: 0,
                      width: "20px",
                      height: "20px",
                      backgroundColor: "#DC2626",
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      marginTop: "2px",
                    }}
                  >
                    <Text
                      as="span"
                      variant="bodySm"
                      fontWeight="bold"
                      color="white"
                    >
                      !
                    </Text>
                  </div>

                  {/* Error Content */}
                  <div style={{ flex: 1 }}>
                    <Text
                      as="h3"
                      variant="headingSm"
                      fontWeight="semibold"
                      color="critical"
                    >
                      Setup Error
                    </Text>
                    <div style={{ marginTop: "4px" }}>
                      <Text as="p" variant="bodyMd" color="critical">
                        {actionData.error}
                      </Text>
                    </div>
                    <div style={{ marginTop: "12px" }}>
                      <Text as="p" variant="bodySm" color="subdued">
                        Please try again or contact support if the issue
                        persists.
                      </Text>
                    </div>
                  </div>
                </div>
              </Banner>
            </div>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
