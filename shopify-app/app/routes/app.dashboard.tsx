import { Page, Layout } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import type { LoaderFunctionArgs } from "@remix-run/node";
import { redirect } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";

import { Dashboard } from "app/components/Dashboard/Dashboard";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  // Get the shop
  const shop = await prisma.shop.findUnique({
    where: { shopDomain: session.shop },
    select: { id: true },
  });

  if (!shop) {
    // Shop doesn't exist, redirect to welcome
    return redirect("/app/step/welcome");
  }

  // Check if user has completed onboarding and has data
  const bundleRecommendations = await prisma.bundleAnalysisResult.findMany({
    where: { shopId: shop.id, isActive: true },
    orderBy: { confidence: "desc" },
    take: 1, // Just check if any exist
  });

  // Check if analysis was ever completed
  const completedJob = await prisma.analysisJob.findFirst({
    where: {
      shopId: shop.id,
      status: "completed",
      completedAt: { not: null },
    },
  });

  // If no analysis completed or no bundle data, redirect to appropriate step
  if (!completedJob) {
    // Never ran analysis - redirect to welcome
    return redirect("/app/step/welcome");
  }

  if (bundleRecommendations.length === 0) {
    // Analysis completed but no results - redirect to widget setup
    return redirect("/app/step/widget-setup");
  }

  // User has completed onboarding and has data - allow access
  return { shopId: shop.id };
};

export default function DashboardPage() {
  return (
    <Page>
      <TitleBar title="Dashboard" />
      <Layout>
        <Dashboard />
      </Layout>
    </Page>
  );
}
