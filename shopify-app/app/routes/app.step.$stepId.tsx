import { useNavigate } from "react-router-dom";
import { Page, Layout, Card, BlockStack, Text, Button } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import {
  useLoaderData,
  useRouteError,
  useOutletContext,
} from "@remix-run/react";
import type { LoaderFunctionArgs, HeadersFunction } from "@remix-run/node";
import { useOnboardingStateMachine } from "../hooks/useOnboardingStateMachine";
import WelcomeStep from "app/components/Onboarding/WelcomeStep";
import AnalysisStep from "app/components/Onboarding/AnalysisStep";
import WidgetSetupStep from "app/components/Onboarding/WidgetSetupStep";
import DashboardStep from "app/components/Onboarding/DashboardStep";
import { boundary } from "@shopify/shopify-app-remix/server";

// Define the context type
type AppContext = {
  session: {
    id: string;
    shop: string;
    hasAccessToken: boolean;
  };
  shopId: string;
};

export const loader = async ({ request, params }: LoaderFunctionArgs) => {
  console.log("🔍 [STEP_ROUTE] Starting step route loader");
  console.log("🔍 [STEP_ROUTE] Request URL:", new URL(request.url).pathname);
  console.log("🔍 [STEP_ROUTE] Params:", params);

  // No need to authenticate here - session comes from parent route
  console.log("🔍 [STEP_ROUTE] Using session from parent route context");

  const { stepId } = params;

  console.log("🔍 [STEP_ROUTE] Step ID:", stepId);

  if (!stepId) {
    throw new Response("Step ID is required", { status: 400 });
  }

  // Get the shop from the parent route context
  // The shopId will be passed down via useOutletContext
  console.log("🔍 [STEP_ROUTE] Step route loader completed");

  return { stepId };
};

export default function StepPage() {
  const { stepId } = useLoaderData<typeof loader>();
  const navigate = useNavigate();
  const { session, shopId } = useOutletContext<AppContext>();

  // Use the state machine
  const { isClient } = useOnboardingStateMachine();

  console.log("🔍 [STEP_ROUTE] Component rendered with session:", session);
  console.log("🔍 [STEP_ROUTE] Shop ID from context:", shopId);

  // Show loading state during SSR or while client is initializing
  if (!isClient) {
    return (
      <Page>
        <TitleBar title="BetterBundle - Loading..." />
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="500" align="center">
                <Text as="h2" variant="headingLg">
                  Loading...
                </Text>
                <Text as="p" variant="bodyMd" alignment="center">
                  Initializing your onboarding experience...
                </Text>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  const renderStep = () => {
    // Render the appropriate step content based on currentStep
    switch (stepId) {
      case "welcome":
        return <WelcomeStep onStartAnalysis={() => {}} />;

      case "analysis":
        return <AnalysisStep onSetupWidget={() => {}} />;

      case "widget-setup":
        return <WidgetSetupStep />;

      case "dashboard":
        return <DashboardStep />;

      default:
        return (
          <BlockStack gap="500" align="center">
            <Text as="h2" variant="headingLg">
              ⚠️ Unknown Step
            </Text>
            <Text as="p" variant="bodyMd" alignment="center">
              This step is not recognized. Please start from the beginning.
            </Text>
            <Button onClick={() => navigate("/app/step/welcome")}>
              Go to Welcome
            </Button>
          </BlockStack>
        );
    }
  };

  return (
    <Page>
      <TitleBar title={`BetterBundle - Step ${stepId}`} />
      <Layout>
        <Layout.Section>
          <Card>{renderStep()}</Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}

// Add error boundary for proper error handling
export function ErrorBoundary() {
  const error = useRouteError();
  console.error("Step route error boundary caught:", error);

  // If it's a redirect response, let Remix handle it
  if (error instanceof Response && error.status === 302) {
    throw error;
  }

  return boundary.error(error);
}

// Add headers function for proper cookie handling
export const headers: HeadersFunction = (headersArgs) => {
  return boundary.headers(headersArgs);
};
