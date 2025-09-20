import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { Page, Layout, BlockStack } from "@shopify/polaris";
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
      <TitleBar title="Billing" />
      <BlockStack gap="500">
        <Layout>
          <Layout.Section>
            <BillingDashboard />
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
