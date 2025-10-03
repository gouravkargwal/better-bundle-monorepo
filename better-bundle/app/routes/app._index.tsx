import { type LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { Page, Layout, BlockStack } from "@shopify/polaris";
import { getShopOnboardingCompleted } from "app/services/shop.service";
import { getDashboardOverview } from "app/services/dashboard.service";
import { OverviewPage } from "app/components/Overview/OverviewPage";
import { TitleBar } from "@shopify/app-bridge-react";
import prisma from "../db.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, redirect } = await authenticate.admin(request);
  const onboardingCompleted = await getShopOnboardingCompleted(session.shop);

  if (!onboardingCompleted) {
    return redirect("/app/onboarding");
  }

  try {
    // Get shop information
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: session.shop },
      select: {
        id: true,
        shop_domain: true,
        currency_code: true,
        plan_type: true,
        created_at: true,
      },
    });

    if (!shop) {
      throw new Error("Shop not found");
    }

    // Get billing plan information
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shop.id,
        status: "active",
      },
      select: {
        id: true,
        name: true,
        type: true,
        status: true,
        configuration: true,
        effective_from: true,
        effective_until: true,
      },
    });

    // Get real dashboard metrics
    let dashboardData = null;
    try {
      dashboardData = await getDashboardOverview(session.shop, "last_30_days");
    } catch (error) {
      console.error("Could not load dashboard data:", error);
      // Continue with null data - overview page will handle this gracefully
    }

    // Get overview metrics
    const overviewData = {
      totalRevenue: dashboardData?.overview?.total_revenue || 0,
      currency: shop.currency_code,
      conversionRate: dashboardData?.overview?.conversion_rate || 0,
      totalRecommendations: dashboardData?.overview?.total_recommendations || 0,
      revenueChange: dashboardData?.overview?.revenue_change || null,
      conversionRateChange:
        dashboardData?.overview?.conversion_rate_change || null,
      recentActivity: dashboardData?.recentActivity || null,
    };

    return json({
      shop: session.shop,
      shopInfo: shop,
      billingPlan,
      overviewData,
    });
  } catch (error) {
    console.error("Error loading overview data:", error);
    return json({
      shop: session.shop,
      error: error instanceof Error ? error.message : "Failed to load data",
    });
  }
};

export default function Index() {
  const data = useLoaderData<typeof loader>();

  return (
    <Page>
      <TitleBar title="Overview" />
      <BlockStack gap="500">
        <Layout>
          <Layout.Section>
            <OverviewPage
              shop={data.shop}
              shopInfo={"shopInfo" in data ? data.shopInfo : null}
              billingPlan={"billingPlan" in data ? data.billingPlan : null}
              overviewData={"overviewData" in data ? data.overviewData : null}
              error={"error" in data ? data.error : undefined}
            />
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
