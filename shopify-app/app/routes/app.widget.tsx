import type { LoaderFunctionArgs } from "@remix-run/node";
import { redirect } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";
import { useLoaderData } from "@remix-run/react";
import Widget from "../components/Widget/Widget";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  // Get the shop
  let shop = await prisma.shop.findUnique({
    where: { shopDomain: session.shop },
    select: { id: true, shopDomain: true },
  });

  // If shop doesn't exist, create it
  if (!shop) {
    console.log(
      `🏪 Creating new shop record for widget config: ${session.shop}`,
    );

    try {
      shop = await prisma.shop.create({
        data: {
          shopDomain: session.shop,
          accessToken: session.accessToken || "",
          email: null,
          planType: "Free",
          currencyCode: null,
          moneyFormat: null,
        },
        select: { id: true, shopDomain: true },
      });

      console.log(`✅ Shop record created for widget: ${shop.id}`);
    } catch (error) {
      console.error("Failed to create shop record for widget:", error);
      throw new Response("Failed to create shop record", { status: 500 });
    }
  }

  // Check if user has completed analysis step
  const completedJob = await prisma.analysisJob.findFirst({
    where: {
      shopId: shop.id,
      status: "completed",
      completedAt: { not: null },
    },
  });

  if (!completedJob) {
    // Analysis not completed - redirect to welcome or analysis step
    const activeJob = await prisma.analysisJob.findFirst({
      where: {
        shopId: shop.id,
        status: { in: ["pending", "processing", "queued"] },
      },
    });

    if (activeJob) {
      // Analysis is running - redirect to analysis step
      return redirect("/app/step/analysis");
    } else {
      // Never started analysis - redirect to welcome
      return redirect("/app/step/welcome");
    }
  }

  // Check if widget setup is needed
  const bundleRecommendations = await prisma.bundleAnalysisResult.findMany({
    where: { shopId: shop.id, isActive: true },
    orderBy: { confidence: "desc" },
    take: 1,
  });

  if (bundleRecommendations.length === 0) {
    // Analysis completed but no results - this is the right place for widget setup
    // Allow access to widget configuration
  } else {
    // User already has data and widget - redirect to dashboard
    return redirect("/app/step/dashboard");
  }

  // Get existing widget configuration
  const widgetConfig = await prisma.widgetConfiguration.findUnique({
    where: { shopId: shop.id },
  });

  return {
    shop,
    widgetConfig: widgetConfig || {
      isEnabled: false,
      theme: "auto",
      position: "product_page",
      title: "Frequently Bought Together",
      showImages: true,
      showIndividualButtons: true,
      showBundleTotal: true,
      globalDiscount: 0,
    },
  };
};

export default function WidgetPage() {
  const { shop, widgetConfig } = useLoaderData<typeof loader>();
  return <Widget shop={shop} initialConfig={widgetConfig} />;
}
