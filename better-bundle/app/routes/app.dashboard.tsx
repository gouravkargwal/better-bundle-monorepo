import type { LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import { useLoaderData, Outlet } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { DashboardPage } from "../features/dashboard/components/DashboardPage";
import { getDateRangeFromUrl } from "../utils/datetime";
import logger from "../utils/logger";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const url = new URL(request.url);

  // If accessing /app/dashboard directly, redirect to revenue tab
  if (url.pathname === "/app/dashboard") {
    const params = new URLSearchParams(url.search);
    const queryString = params.toString();
    const query = queryString ? `?${queryString}` : "";

    return redirect(`/app/dashboard/revenue${query}`);
  }

  const { session } = await authenticate.admin(request);

  // Check actual Gorse readiness so returning users skip the modal
  let recommendationsReady = false;
  try {
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: session.shop },
      select: { id: true },
    });
    if (shopRecord) {
      const backendUrl = process.env.PYTHON_WORKER_API_URL;
      if (backendUrl) {
        const resp = await fetch(
          `${backendUrl}/api/v1/gorse/status/${shopRecord.id}`,
          { signal: AbortSignal.timeout(5_000) },
        );
        if (resp.ok) {
          const data = await resp.json();
          logger.info(
            { gorseStatus: data, shopId: shopRecord.id },
            "Gorse readiness check in dashboard loader",
          );
          const featuresSynced =
            data?.feature_utilization?.feature_counts?.product_features || 0;
          const gorseHealthy = data?.gorse_health?.success === true;
          recommendationsReady = gorseHealthy && featuresSynced > 0;
        } else {
          logger.warn(
            { status: resp.status, shopId: shopRecord.id },
            "Gorse status endpoint returned non-OK",
          );
        }
      }
    }
  } catch (err) {
    logger.warn({ err }, "Gorse readiness check failed in dashboard loader");
  }

  const { startDate, endDate } = getDateRangeFromUrl(url);
  return json({ startDate, endDate, recommendationsReady });
};

export default function Dashboard() {
  const { startDate, endDate, recommendationsReady } =
    useLoaderData<typeof loader>();
  return (
    <DashboardPage
      startDate={startDate}
      endDate={endDate}
      recommendationsReady={recommendationsReady}
    >
      <Outlet />
    </DashboardPage>
  );
}
