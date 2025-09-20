import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { Page, Layout, Text, BlockStack } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { BillingDashboard } from "../components/Billing/BillingDashboard";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  return json({
    shop,
  });
};

export default function BillingPage() {
  useLoaderData<typeof loader>();

  return (
    <Page>
      <TitleBar title="Billing & Performance" />
      <BlockStack gap="500">
        {/* Header Section */}
        <Layout>
          <Layout.Section>
            <div
              style={{
                padding: "24px",
                backgroundColor: "#F0F9FF",
                borderRadius: "12px",
                border: "1px solid #BAE6FD",
              }}
            >
              <div style={{ color: "#0C4A6E" }}>
                <Text as="h1" variant="heading2xl" fontWeight="bold">
                  💰 Billing & Performance
                </Text>
              </div>
              <div style={{ marginTop: "8px" }}>
                <Text as="p" variant="bodyLg" tone="subdued">
                  Track your pay-as-performance billing and revenue attribution
                </Text>
              </div>
              <div style={{ marginTop: "12px" }}>
                <Text as="p" variant="bodyMd" tone="subdued">
                  Monitor your billing performance, view invoices, and track how
                  your recommendations are driving revenue for your store.
                </Text>
              </div>
            </div>
          </Layout.Section>
        </Layout>

        {/* Main Content */}
        <Layout>
          <Layout.Section>
            <BillingDashboard />
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
