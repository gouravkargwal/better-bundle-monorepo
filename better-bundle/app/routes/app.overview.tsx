// app/routes/app.overview.tsx
import { type LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { OverviewService } from "../features/overview/services/overview.service";
import { OverviewPage } from "../features/overview/components/OverviewPage";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    const overviewService = new OverviewService();
    const data = await overviewService.getOverviewData(session.shop);
    return json(data);
  } catch (error) {
    console.error("Failed to load overview data:", error);
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
  return (
    <OverviewPage data={data} error={"error" in data ? data : undefined} />
  );
}
