// app/routes/app.overview.tsx
import { type LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData, useRevalidator } from "@remix-run/react";
import { useEffect, useRef } from "react";
import { authenticate } from "../shopify.server";
import { OverviewService } from "../features/overview/services/overview.service";
import { OverviewPage } from "../features/overview/components/OverviewPage";
import logger from "../utils/logger";

const POLL_INTERVAL_MS = 15_000; // 15 seconds

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    const overviewService = new OverviewService();
    const data = await overviewService.getOverviewData(session.shop);
    return json(data);
  } catch (error) {
    logger.error({ error, shop: session.shop }, "Failed to load overview data");
    return json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Failed to load overview data",
      },
      { status: 500 },
    );
  }
};

export default function OverviewRoute() {
  const data = useLoaderData<typeof loader>();
  const { revalidate } = useRevalidator();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isSetupComplete =
    "setupStatus" in data && data.setupStatus?.isSetupComplete;

  useEffect(() => {
    if (isSetupComplete) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }

    intervalRef.current = setInterval(() => {
      revalidate();
    }, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isSetupComplete, revalidate]);

  return (
    <OverviewPage data={data} error={"error" in data ? data : undefined} />
  );
}
