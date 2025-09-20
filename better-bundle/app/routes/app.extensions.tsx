import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import {
  Page,
  Layout,
  BlockStack,
  Text,
  Button,
  InlineGrid,
} from "@shopify/polaris";
import { ExtensionManager } from "../components/Extensions/ExtensionManager";
import prisma from "../db.server";
import { TitleBar } from "@shopify/app-bridge-react";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    // Get shop ID from database
    const shop = await prisma.shop.findUnique({
      where: { shopDomain: session.shop },
    });

    let extensions: Record<string, any> = {};
    if (shop) {
      // Get active extensions (last 24 hours)
      const cutoffTime = new Date();
      cutoffTime.setHours(cutoffTime.getHours() - 24);

      const results = await (prisma as any).extensionActivity.findMany({
        where: {
          shopId: shop.id,
          lastSeen: {
            gt: cutoffTime,
          },
          extensionType: {
            in: ["apollo", "phoenix", "venus"],
          },
        },
        orderBy: {
          lastSeen: "desc",
        },
      });

      // Group by extension type
      for (const result of results) {
        const extType = result.extensionType;

        if (!extensions[extType]) {
          extensions[extType] = {
            active: true,
            last_seen: result.lastSeen.toISOString(),
            app_blocks: [],
          };
        }

        // Add app block info if available
        if (result.appBlockTarget && result.appBlockLocation) {
          extensions[extType].app_blocks.push({
            target: result.appBlockTarget,
            location: result.appBlockLocation,
            page_url: result.pageUrl,
            extension_uid: result.extensionUid,
          });
        }
      }

      // Ensure all extension types are represented
      const allTypes = ["apollo", "phoenix", "venus"];
      for (const extType of allTypes) {
        if (!extensions[extType]) {
          extensions[extType] = {
            active: false,
            last_seen: null,
            app_blocks: [],
          };
        }
      }
    }

    return json({
      shopDomain: session.shop,
      extensions,
    });
  } catch (error) {
    console.error("Failed to fetch extension activity:", error);
    return json({
      shopDomain: session.shop,
      extensions: {},
    });
  }
};

export default function WidgetConfig() {
  const { shopDomain, extensions } = useLoaderData<typeof loader>();

  return (
    <Page>
      <TitleBar title="Extensions" />
      <Layout>
        <Layout.Section>
          <BlockStack gap="500">
            <ExtensionManager extensions={extensions} />

            <div
              style={{
                padding: "24px",
                backgroundColor: "#FEF3C7",
                borderRadius: "12px",
                border: "1px solid #FCD34D",
              }}
            >
              <div style={{ color: "#92400E" }}>
                <Text as="h2" variant="headingLg" fontWeight="bold">
                  🎨 Theme Integration Help
                </Text>
              </div>
              <div style={{ marginTop: "8px" }}>
                <Text as="p" variant="bodyMd" tone="subdued">
                  Need help integrating BetterBundle widgets into your theme?
                </Text>
              </div>
              <div style={{ marginTop: "16px" }}>
                <InlineGrid columns={{ xs: 1, sm: 2 }} gap="300">
                  <Button
                    variant="secondary"
                    size="slim"
                    onClick={() =>
                      window.open(
                        `https://${shopDomain}/admin/themes`,
                        "_blank",
                      )
                    }
                    fullWidth
                  >
                    Open Theme Editor
                  </Button>
                  <Button
                    variant="primary"
                    size="slim"
                    onClick={() =>
                      window.open(
                        `https://${shopDomain}/admin/themes/current/editor`,
                        "_blank",
                      )
                    }
                    fullWidth
                  >
                    Customize Theme
                  </Button>
                </InlineGrid>
              </div>
            </div>
          </BlockStack>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
