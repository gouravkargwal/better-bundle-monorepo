import {
  json,
  type LoaderFunctionArgs,
  type ActionFunctionArgs,
} from "@remix-run/node";
import { useLoaderData, useFetcher } from "@remix-run/react";
import { useEffect } from "react";
import { authenticate } from "../shopify.server";
import { Page, Layout, BlockStack } from "@shopify/polaris";
import { ExtensionSetupGuide } from "../components/Extensions/ExtensionSetupGuide";
import { TitleBar } from "@shopify/app-bridge-react";
import prisma from "../db.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  return json({ shopDomain: session.shop });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  await prisma.shops.update({
    where: { shop_domain: session.shop },
    data: { setup_guide_visited: true },
  });
  return json({ ok: true });
};

export default function ExtensionsPage() {
  const { shopDomain } = useLoaderData<typeof loader>();
  const fetcher = useFetcher();

  useEffect(() => {
    // Mark setup guide as visited once when the page loads
    if (fetcher.state === "idle" && fetcher.data === undefined) {
      fetcher.submit(null, { method: "post" });
    }
  }, [fetcher]);

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
