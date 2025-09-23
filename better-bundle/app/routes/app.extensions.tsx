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
  Card,
} from "@shopify/polaris";
import { SettingsIcon } from "@shopify/polaris-icons";
import { ExtensionManager } from "../components/Extensions/ExtensionManager";
import prisma from "../db.server";
import { TitleBar } from "@shopify/app-bridge-react";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    // Get shop ID from database
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: session.shop },
    });

    let extensions: Record<string, any> = {};
    if (shop) {
      // Get active extensions (last 24 hours)
      const cutoffTime = new Date();
      cutoffTime.setHours(cutoffTime.getHours() - 24);

      const results = await prisma.extension_activities.findMany({
        where: {
          shop_id: shop.id,
          last_seen: {
            gt: cutoffTime,
          },
          extension_type: {
            in: ["apollo", "phoenix", "venus"],
          },
        },
        orderBy: {
          last_seen: "desc",
        },
      });

      // Group by extension type
      for (const result of results) {
        const extType = result.extension_type;

        if (!extensions[extType]) {
          extensions[extType] = {
            active: true,
            last_seen: result.last_seen.toISOString(),
            app_blocks: [],
          };
        }

        // Add app block info if available
        if (result.app_block_target && result.app_block_location) {
          extensions[extType].app_blocks.push({
            target: result.app_block_target,
            location: result.app_block_location,
            page_url: result.page_url,
            extension_uid: result.extension_uid,
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
      <BlockStack gap="300">
        {/* Hero Section */}
        <div
          style={{
            padding: "24px 20px",
            background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            borderRadius: "16px",
            color: "white",
            textAlign: "center",
            position: "relative",
            overflow: "hidden",
            boxShadow:
              "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
          }}
        >
          <div style={{ position: "relative", zIndex: 2 }}>
            {/* Hero Badge */}
            <div style={{ marginBottom: "12px" }}>
              <div
                style={{
                  display: "inline-block",
                  padding: "6px 12px",
                  backgroundColor: "rgba(255, 255, 255, 0.2)",
                  border: "1px solid rgba(255, 255, 255, 0.3)",
                  color: "white",
                  fontWeight: "600",
                  borderRadius: "6px",
                  fontSize: "12px",
                }}
              >
                🎨 Extension Manager
              </div>
            </div>

            {/* Main Headline */}
            <div
              style={{
                fontSize: "2rem",
                lineHeight: "1.2",
                marginBottom: "8px",
                background: "linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
                fontWeight: "bold",
              }}
            >
              Manage Your Extensions
            </div>

            {/* Subheadline */}
            <div
              style={{
                marginBottom: "12px",
                maxWidth: "500px",
                margin: "0 auto 12px",
              }}
            >
              <div
                style={{
                  color: "rgba(255,255,255,0.95)",
                  lineHeight: "1.4",
                  fontWeight: "500",
                  fontSize: "1rem",
                }}
              >
                Configure and monitor your AI recommendation extensions
              </div>
            </div>

            {/* Enhanced Decorative elements */}
            <div
              style={{
                position: "absolute",
                top: "-50px",
                right: "-50px",
                width: "150px",
                height: "150px",
                background:
                  "radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)",
                borderRadius: "50%",
                zIndex: 1,
              }}
            />
            <div
              style={{
                position: "absolute",
                bottom: "-40px",
                left: "-40px",
                width: "120px",
                height: "120px",
                background:
                  "radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 70%)",
                borderRadius: "50%",
                zIndex: 1,
              }}
            />
          </div>
        </div>

        <Layout>
          <Layout.Section>
            <BlockStack gap="300">
              <ExtensionManager extensions={extensions} />

              <Card>
                <div style={{ padding: "20px" }}>
                  <BlockStack gap="300">
                    <div
                      style={{
                        padding: "20px",
                        backgroundColor: "#FEF3C7",
                        borderRadius: "12px",
                        border: "1px solid #FCD34D",
                      }}
                    >
                      <div style={{ color: "#92400E" }}>
                        <Text as="h3" variant="headingMd" fontWeight="bold">
                          🎨 Theme Integration Help
                        </Text>
                      </div>
                      <div style={{ marginTop: "8px" }}>
                        <Text as="p" variant="bodyMd" tone="subdued">
                          Need help integrating BetterBundle widgets into your
                          theme?
                        </Text>
                      </div>
                    </div>

                    <InlineGrid columns={{ xs: 1, sm: 2 }} gap="300">
                      <Button
                        variant="secondary"
                        size="large"
                        icon={SettingsIcon}
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
                        size="large"
                        icon={SettingsIcon}
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
                  </BlockStack>
                </div>
              </Card>
            </BlockStack>
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
