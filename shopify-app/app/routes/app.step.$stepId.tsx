import { useNavigate } from "react-router-dom";
import { Page, Layout, Card, BlockStack, Text, Button } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { useLoaderData } from "@remix-run/react";
import type { LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";
import { useOnboardingStateMachine } from "../hooks/useOnboardingStateMachine";
import WelcomeStep from "app/components/Onboarding/WelcomeStep";
import AnalysisStep from "app/components/Onboarding/AnalysisStep";
import WidgetSetupStep from "app/components/Onboarding/WidgetSetupStep";
import DashboardStep from "app/components/Onboarding/DashboardStep";

export const loader = async ({ request, params }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const { stepId } = params;

  // Get the shop
  let shop = await prisma.shop.findUnique({
    where: { shopDomain: session.shop },
    select: { id: true },
  });

  // If shop doesn't exist, create it
  if (!shop) {
    console.log(`🏪 Creating new shop record for step: ${session.shop}`);

    try {
      shop = await prisma.shop.create({
        data: {
          shopId: session.shop,
          shopDomain: session.shop,
          accessToken: session.accessToken || "",
          email: null,
          planType: "Free",
          currencyCode: null,
          moneyFormat: null,
        },
        select: { id: true },
      });

      console.log(`✅ Shop record created for step: ${shop.id}`);
    } catch (error) {
      console.error("Failed to create shop record for step:", error);
      throw new Response("Failed to create shop record", { status: 500 });
    }
  }

  // Get current step data
  const currentStep = await getStepData(shop.id, stepId);

  return { currentStep, shopId: shop.id };
};

async function getStepData(shopId: string, stepId: string) {
  switch (stepId) {
    case "welcome":
      return { type: "welcome" };

    case "analysis":
      const activeJob = await prisma.analysisJob.findFirst({
        where: { shopId, status: { in: ["pending", "processing", "queued"] } },
        select: { jobId: true, status: true, progress: true },
      });
      return { type: "analysis", activeJob };

    case "widget-setup":
      const completedJob = await prisma.analysisJob.findFirst({
        where: { shopId, status: "completed" },
      });
      return { type: "widget_setup", completedJob };

    case "dashboard":
      const [bundleRecommendations, orderData, productData] = await Promise.all(
        [
          prisma.bundleAnalysisResult.findMany({
            where: { shopId, isActive: true },
            orderBy: { confidence: "desc" },
            take: 10,
          }),
          prisma.orderData.findMany({
            where: { shopId },
            select: { totalAmount: true, orderDate: true },
          }),
          prisma.productData.count({ where: { shopId, isActive: true } }),
        ],
      );

      const totalRevenue = orderData.reduce(
        (sum, order) => sum + order.totalAmount,
        0,
      );
      const totalOrders = orderData.length;

      return {
        type: "dashboard",
        bundleRecommendations,
        metrics: { totalRevenue, totalOrders, totalProducts: productData },
      };

    default:
      throw new Response("Step not found", { status: 404 });
  }
}

export default function StepPage() {
  const { currentStep } = useLoaderData<typeof loader>();
  const navigate = useNavigate();
  // Use the state machine
  const { isClient } = useOnboardingStateMachine();

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
    switch (currentStep) {
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
      <TitleBar title={`BetterBundle - Step ${currentStep}`} />
      <Layout>
        <Layout.Section>
          <Card>{renderStep()}</Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
