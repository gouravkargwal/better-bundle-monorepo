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

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  return json({
    shopDomain: session.shop,
  });
};

export default function WidgetConfig() {
  const { shopDomain } = useLoaderData<typeof loader>();

  return (
    <Page>
      <Layout>
        <Layout.Section>
          <BlockStack gap="500">
            {/* Header */}
            <div
              style={{
                padding: "24px",
                backgroundColor: "#ECFDF5",
                borderRadius: "12px",
                border: "1px solid #A7F3D0",
              }}
            >
              <div style={{ color: "#065F46" }}>
                <Text as="h2" variant="headingLg" fontWeight="bold">
                  ⚙️ Extension Management
                </Text>
              </div>
              <div style={{ marginTop: "8px" }}>
                <Text as="p" variant="bodyMd" tone="subdued">
                  Learn about your BetterBundle extensions and how to activate
                  them
                </Text>
              </div>
            </div>

            {/* Extension Manager */}
            <ExtensionManager />

            {/* Theme Integration Help */}
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
