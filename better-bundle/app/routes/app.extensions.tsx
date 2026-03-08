import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { Page, Layout, BlockStack } from "@shopify/polaris";
import { ExtensionSetupGuide } from "../components/Extensions/ExtensionSetupGuide";
import { TitleBar } from "@shopify/app-bridge-react";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  return json({ shopDomain: session.shop });
};

export default function ExtensionsPage() {
  const { shopDomain } = useLoaderData<typeof loader>();

  return (
    <Page>
      <TitleBar title="Extension Setup Guide" />
      <BlockStack gap="400">
        <Layout>
          <Layout.Section>
            <ExtensionSetupGuide shopDomain={shopDomain} />
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
