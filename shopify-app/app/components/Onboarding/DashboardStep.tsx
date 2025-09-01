import { BlockStack } from "@shopify/polaris";
import { Link } from "@remix-run/react";

export default function DashboardStep() {
  return (
    <BlockStack gap="500">
      <Link to="/app/dashboard">Go to Dashboard</Link>
    </BlockStack>
  );
}
