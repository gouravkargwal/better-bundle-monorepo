import type { LoaderFunctionArgs, ActionFunctionArgs } from "@remix-run/node";
import { useActionData, Form, json } from "@remix-run/react";
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

  return (
    <Page>
      <TitleBar title="Welcome to BetterBundle!" />

      <BlockStack gap="600">
        <div
          style={{
            padding: "64px 32px",
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
              <div style={{ color: "rgba(255,255,255,0.9)" }}>
                <Text as="p" variant="headingMd">
                  Transform your store with AI-powered product recommendations
                </Text>
              </div>
            </div>
            <div style={{ marginTop: "24px" }}>
              <Badge size="large" tone="info">
                Start earning more revenue in minutes
              </Badge>
            </div>

            {/* Pay-As-Performance Highlight */}
            <div
              style={{
                marginTop: "32px",
                padding: "24px",
                backgroundColor: "rgba(255,255,255,0.15)",
                borderRadius: "12px",
                border: "2px solid rgba(255,255,255,0.3)",
              }}
            >
              <Text as="h3" variant="headingLg" fontWeight="bold">
                💳 Pay-As-Performance Model
              </Text>
              <div style={{ marginTop: "8px" }}>
                <div style={{ color: "rgba(255,255,255,0.9)" }}>
                  <Text as="p" variant="bodyLg">
                    Start with $200 free credits • Only pay when you see results
                    • No upfront costs
                  </Text>
                </div>
              </div>
              <div style={{ marginTop: "12px" }}>
                <Badge size="large" tone="success">
                  Risk-free trial with guaranteed results
                </Badge>
              </div>
            </div>

            {/* Call to Action Button */}
            <div style={{ marginTop: "32px" }}>
              <Form method="post">
                <Button
                  submit
                  variant="primary"
                  size="large"
                  icon={ArrowRightIcon}
                  loading={false}
                >
                  Start Your Free Trial Now
                </Button>
              </Form>
              <div style={{ marginTop: "16px" }}>
                <div style={{ color: "rgba(255,255,255,0.8)" }}>
                  <Text as="p" variant="bodySm">
                    Setup takes less than 2 minutes • No coding required
                  </Text>
                </div>
              </div>
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
        <FeatureCard />
        <Benefits />

        {/* Error Display Section */}
        {actionData?.error && (
          <Card>
            <div style={{ padding: "24px" }}>
              <Banner tone="critical">
                <div
                  style={{
                    padding: "16px",
                    backgroundColor: "#FEF2F2",
                    border: "2px solid #FCA5A5",
                    borderRadius: "8px",
                  }}
                >
                  <Text as="p" variant="bodyMd" fontWeight="semibold">
                    {actionData.error}
                  </Text>
                </div>
              </Banner>
            </div>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
