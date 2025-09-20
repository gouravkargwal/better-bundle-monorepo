import type { LoaderFunctionArgs, ActionFunctionArgs } from "@remix-run/node";
import { useActionData, Form, json } from "@remix-run/react";
import { Page, Card, Button, BlockStack, Text, Banner } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
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

  return (
    <Page>
      <TitleBar title="Welcome to BetterBundle!" />

      <Card>
        <BlockStack gap="400">
          <Text as="h1" variant="heading2xl">
            🎉 Let's get you started!
          </Text>

          <Text as="p" variant="bodyLg">
            Click the button below to complete your setup and start using
            BetterBundle.
          </Text>

          {actionData?.error && (
            <Banner tone="critical">
              <Text as="p">{actionData.error}</Text>
            </Banner>
          )}

          <Form method="post">
            <Button submit variant="primary" size="large" loading={false}>
              Complete Setup & Start Earning
            </Button>
          </Form>
        </BlockStack>
      </Card>
    </Page>
  );
}
