import type { LoaderFunctionArgs } from "@remix-run/node";
import { redirect } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  // Check for existing shop record
  let shop = await prisma.shop.findUnique({
    where: { shopDomain: session.shop },
    select: { id: true },
  });

  // If shop doesn't exist, create it
  if (!shop) {
    console.log(`🏪 Creating new shop record for: ${session.shop}`);

    try {
      // Create shop record with basic info
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

      console.log(`✅ Shop record created: ${shop.id}`);
    } catch (error) {
      console.error("Failed to create shop record:", error);
      // If we can't create the shop, still redirect to welcome
      return redirect("/app/step/welcome");
    }
  }

  // Check for active analysis job
  const activeJob = await prisma.analysisJob.findFirst({
    where: {
      shopId: shop.id,
      status: { in: ["pending", "processing", "queued"] },
    },
    orderBy: { createdAt: "desc" },
    select: { jobId: true, status: true, progress: true },
  });

  // Check for bundle analysis results
  const bundleRecommendations = await prisma.bundleAnalysisResult.findMany({
    where: { shopId: shop.id, isActive: true },
    orderBy: { confidence: "desc" },
    take: 10,
  });

  // Determine user step based on actual data
  let userStep:
    | "new_user"
    | "analysis_running"
    | "analysis_complete_no_widget"
    | "has_data";

  if (activeJob) {
    // Step 1: Analysis is running
    userStep = "analysis_running";
  } else if (bundleRecommendations.length === 0) {
    // No analysis results - check if analysis was ever run
    const completedJob = await prisma.analysisJob.findFirst({
      where: {
        shopId: shop.id,
        status: "completed",
        completedAt: { not: null },
      },
    });

    if (completedJob) {
      // Step 2: Analysis completed but no results (need widget setup)
      userStep = "analysis_complete_no_widget";
    } else {
      // Step 0: New user, never run analysis
      userStep = "new_user";
    }
  } else {
    // Step 3: Has bundle data - show dashboard
    userStep = "has_data";
  }

  // Redirect based on user step
  if (activeJob) {
    return redirect("/app/step/analysis");
  }

  if (userStep === "has_data") {
    return redirect("/app/step/dashboard");
  }

  if (userStep === "analysis_complete_no_widget") {
    return redirect("/app/step/widget-setup");
  }

  // For new users, redirect to welcome step
  return redirect("/app/step/welcome");
};

export default function Index() {
  // This component should never render due to redirects in loader
  return null;
}
