import { useLoaderData } from "@remix-run/react";
import { loadRevenueData } from "../features/dashboard/services/revenue.service";
import { BlockStack } from "@shopify/polaris";
import { RevenueKPICards } from "../features/dashboard/components/KPICards";

export const loader = loadRevenueData;

export default function RevenueTab() {
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
      <RevenueKPICards
        data={data.overview}
        attributedMetrics={data.attributedMetrics}
      />
    </BlockStack>
  );
}
