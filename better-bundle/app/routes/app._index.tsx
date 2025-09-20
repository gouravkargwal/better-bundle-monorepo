import type { LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { getDashboardOverview } from "../services/dashboard.service";
import { WelcomePage } from "../components/WelcomePage";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    // Get basic dashboard data for the welcome page
    const dashboardData = await getDashboardOverview(session.shop);
    return {
      dashboardData,
      shop: session.shop,
      isNewUser: !dashboardData || dashboardData.overview.total_revenue === 0,
    };
  } catch (error) {
    console.error("Welcome page loader error:", error);
    return {
      dashboardData: null,
      shop: session.shop,
      isNewUser: true,
      error: "Failed to load dashboard data",
    };
  }
};

export default function Index() {
  const { dashboardData, shop, isNewUser } = useLoaderData<typeof loader>();

  return (
    <WelcomePage
      dashboardData={dashboardData}
      shop={shop}
      isNewUser={isNewUser}
    />
  );
}
