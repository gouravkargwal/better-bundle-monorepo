import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { Page, Layout, Text, BlockStack } from "@shopify/polaris";
import { BillingDashboard } from "../components/billing/BillingDashboard";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  return json({
    shop,
  });
};

export default function BillingPage() {
  const { shop } = useLoaderData<typeof loader>();

  return (
    <Page
      title="Billing & Performance"
      subtitle="Track your pay-as-performance billing and revenue attribution"
      fullWidth
    >
      <Layout>
        <Layout.Section>
          <BlockStack gap="400">
            <Text as="p" variant="bodyMd" tone="subdued">
              Monitor your billing performance, view invoices, and track how
              your recommendations are driving revenue for your store.
            </Text>

            <BillingDashboard />
          </BlockStack>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
