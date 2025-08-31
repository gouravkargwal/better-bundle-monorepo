import React from "react";
import type { LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { DashboardState } from "../shared/components/DashboardState";
import { useAnalysis } from "../hooks/useAnalysis";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  return null;
};

export default function Index() {
  const { state, progress, error, startAnalysis, handleRetry } = useAnalysis();

  return (
    <DashboardState
      state={state}
      error={error || undefined}
      progress={progress}
      onStartAnalysis={startAnalysis}
      onRetry={handleRetry}
    />
  );
}
