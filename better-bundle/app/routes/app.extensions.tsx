import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { Page, Layout, BlockStack } from "@shopify/polaris";
import { ExtensionSetupGuide } from "../components/Extensions/ExtensionSetupGuide";
import prisma from "../db.server";
import { TitleBar } from "@shopify/app-bridge-react";
import logger from "../utils/logger";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: session.shop },
    });

    // Mark setup guide as visited
    if (shop && !shop.setup_guide_visited) {
      await prisma.shops.update({
        where: { shop_domain: session.shop },
        data: { setup_guide_visited: true },
      });
    }

    return json({ shopDomain: session.shop });
  } catch (error) {
    logger.error(
      { error, shop: session.shop },
      "Failed to load extensions page",
    );
    return json({ shopDomain: session.shop });
  }
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
