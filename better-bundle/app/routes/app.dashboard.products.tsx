import { useLoaderData } from "@remix-run/react";
import { loadProductsData } from "../features/dashboard/services/products.service";
import { TopProductsTable } from "../features/dashboard/components/TopProductsTable";
import { BlockStack } from "@shopify/polaris";

export const loader = loadProductsData;

export default function ProductsTab() {
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
      <TopProductsTable data={data.topProducts} />
    </BlockStack>
  );
}
