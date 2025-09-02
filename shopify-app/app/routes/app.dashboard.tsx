import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";
import { Page } from "@shopify/polaris";
import { Dashboard } from "app/components/Dashboard/Dashboard";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  // Get shop info
  const shop = await prisma.shop.findFirst({
    where: { shopDomain: session.shop },
  });

  // Get latest analysis job
  const latestJob = await prisma.analysisJob.findFirst({
    where: { shopId: shop?.id },
    orderBy: { createdAt: "desc" },
  });

  return json({ shop, latestJob });
};

export default function DashboardPage() {
  const { shop } = useLoaderData<typeof loader>();

  return (
    <Page title="BetterBundle Dashboard">
      <Dashboard />
    </Page>
  );
}
