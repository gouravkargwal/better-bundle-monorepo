import { useLoaderData } from "@remix-run/react";
import { loadActivityData } from "../features/dashboard/services/activity.service";
import { RecentActivity } from "../features/dashboard/components/RecentActivity";
import { BlockStack } from "@shopify/polaris";

export const loader = loadActivityData;

export default function ActivityTab() {
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
      <RecentActivity data={data.recentActivity} />
    </BlockStack>
  );
}
