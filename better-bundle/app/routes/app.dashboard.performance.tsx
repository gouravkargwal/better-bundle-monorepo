import { useLoaderData } from "@remix-run/react";
import { loadPerformanceData } from "../features/dashboard/services/performance.service";
import { BlockStack } from "@shopify/polaris";
import { PerformanceKPICards } from "app/features/dashboard/components/KPICards";

export const loader = loadPerformanceData;

export default function PerformanceTab() {
  const data = useLoaderData<typeof loader>();

  if ("error" in data) {
    return (
      <BlockStack gap="300">
        <div>Error: {data.error}</div>
      </BlockStack>
    );
  }

  return (
    <BlockStack gap="300">
      <PerformanceKPICards data={data.performance} />
    </BlockStack>
  );
}
