import React from "react";
import type { LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";
import { DashboardState } from "../shared/components/DashboardState";
import { useAnalysis } from "../hooks/useAnalysis";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  // Check for existing analysis jobs
  const shop = await prisma.shop.findUnique({
    where: { shopDomain: session.shop },
    select: { id: true },
  });

  if (shop) {
    const activeJob = await prisma.analysisJob.findFirst({
      where: {
        shopId: shop.id,
        status: { in: ["pending", "processing"] },
      },
      orderBy: { createdAt: "desc" },
      select: { jobId: true, status: true, progress: true },
    });

    if (activeJob) {
      return { activeJob };
    }
  }

  return null;
};

export default function Index() {
  const loaderData = useLoaderData<typeof loader>();
  const { state, progress, error, startAnalysis, handleRetry, isSubmitting } =
    useAnalysis(loaderData?.activeJob);

  // If there's an active job from the loader, show loading state
  const currentState = loaderData?.activeJob ? "loading" : state;
  const currentProgress = loaderData?.activeJob?.progress || progress;
  const currentJobId = loaderData?.activeJob?.jobId || null;

  return (
    <DashboardState
      state={currentState}
      error={error || undefined}
      progress={currentProgress}
      jobId={currentJobId}
      isSubmitting={isSubmitting}
      onStartAnalysis={startAnalysis}
      onRetry={handleRetry}
    />
  );
}
