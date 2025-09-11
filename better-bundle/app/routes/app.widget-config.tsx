import {
  json,
  type ActionFunctionArgs,
  type LoaderFunctionArgs,
} from "@remix-run/node";
import { useLoaderData, useActionData, useNavigation } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import {
  getWidgetConfiguration,
  createDefaultConfiguration,
} from "../services/widget-config.service";
import { Page, Layout, InlineGrid, BlockStack } from "@shopify/polaris";
import { WidgetConfigForm } from "../components/Widget/WidgetConfigSection";
import { WidgetPreviewSection } from "../components/Widget/WidgetPreviewSection";
import { WidgetInstallationSection } from "../components/Widget/WidgetInstallationSection";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  console.log("🔧 Widget config loader - shop:", session.shop);

  // Get widget configuration (create default if doesn't exist)
  let config = await getWidgetConfiguration(session.shop);
  console.log("📋 Existing config found:", !!config);

  if (!config) {
    console.log("⚙️ Creating default configuration for:", session.shop);
    try {
      config = await createDefaultConfiguration(session.shop);
      console.log("✅ Default configuration created successfully");
    } catch (error) {
      console.error("❌ Error creating default configuration:", error);
      throw error;
    }
  }

  return json({
    config,
    shopDomain: session.shop,
  });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  await authenticate.admin(request);

  const formData = await request.formData();
  const action = formData.get("_action") as string;

  if (action === "update") {
    // Forward to the API route
    const response = await fetch(
      `${request.url.replace("/app/widget-config", "/app/api/widget-config")}`,
      {
        method: "POST",
        body: formData,
      },
    );

    const result = await response.json();
    return json(result);
  }

  return json({ success: false, error: "Invalid action" });
};

export default function WidgetConfig() {
  const { config } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const navigation = useNavigation();
  const isSubmitting = navigation.state === "submitting";

  // Page configurations for preview
  const pageConfigs = [
    {
      key: "product_page",
      label: "Product Pages",
      title: config.productPageTitle || "You might also like",
    },
    {
      key: "cart_page",
      label: "Cart Page",
      title: config.cartPageTitle || "Frequently bought together",
    },
    {
      key: "homepage",
      label: "Homepage",
      title: config.homepageTitle || "Popular products",
    },
    {
      key: "collection",
      label: "Collection Pages",
      title: config.collectionPageTitle || "Similar products",
    },
  ];

  return (
    <Page>
      <Layout>
        <Layout.Section>
          <InlineGrid columns={{ xs: 1, md: 2 }} gap="600">
            {/* Left Column - Configuration Form */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                height: "100%",
              }}
            >
              <WidgetConfigForm
                config={config}
                actionData={actionData}
                isSubmitting={isSubmitting}
              />
            </div>

            {/* Right Column - Preview & Installation */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                height: "100%",
              }}
            >
              <BlockStack gap="500">
                <WidgetPreviewSection
                  selectedPageType=""
                  pageConfigs={pageConfigs}
                />
                <WidgetInstallationSection />
              </BlockStack>
            </div>
          </InlineGrid>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
