import { useState } from "react";
import type { LoaderFunctionArgs, ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData, useFetcher } from "@remix-run/react";
import {
  Page,
  Layout,
  Text,
  Card,
  BlockStack,
  InlineStack,
  Button,
  TextField,
  Select,
  Checkbox,
  Banner,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shopId = session.shop;

  // Get shop settings
  const shop = await prisma.shop.findUnique({
    where: { shopDomain: shopId },
    select: { planType: true, lastAnalysisAt: true },
  });

  return json({
    shop,
    // Default settings
    settings: {
      minSupport: 0.01,
      minConfidence: 0.1,
      minLift: 2.0,
      analysisWindow: 180,
      widgetPlacement: "product_page",
      autoRefresh: true,
    },
  });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shopId = session.shop;

  const formData = await request.formData();
  const action = formData.get("action");

  if (action === "update_settings") {
    return json({ success: true, message: "Settings updated successfully" });
  }

  if (action === "refresh_analysis") {
    return json({ success: true, message: "Analysis refresh started" });
  }

  return json({ success: false, error: "Invalid action" });
};

export default function Settings() {
  const { shop, settings } = useLoaderData<typeof loader>();
  const fetcher = useFetcher();
  const [localSettings, setLocalSettings] = useState(settings);

  const handleSettingChange = (key: string, value: unknown) => {
    setLocalSettings((prev) => ({ ...prev, [key]: value }));
  };

  const saveSettings = () => {
    fetcher.submit(
      { action: "update_settings", ...localSettings },
      { method: "POST" },
    );
  };

  const refreshAnalysis = () => {
    fetcher.submit({ action: "refresh_analysis" }, { method: "POST" });
  };

  return (
    <Page>
      <TitleBar title="Settings" />

      <Layout>
        <Layout.Section>
          <BlockStack gap="500">
            {/* Account Information */}
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Account Information
                </Text>
                <BlockStack gap="200">
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodyMd">
                      Plan Type
                    </Text>
                    <Text as="span" variant="bodyMd">
                      {shop?.planType || "Free"}
                    </Text>
                  </InlineStack>
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodyMd">
                      Last Analysis
                    </Text>
                    <Text as="span" variant="bodyMd">
                      {shop?.lastAnalysisAt
                        ? new Date(shop.lastAnalysisAt).toLocaleDateString()
                        : "Never"}
                    </Text>
                  </InlineStack>
                </BlockStack>
              </BlockStack>
            </Card>

            {/* Analysis Settings */}
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Bundle Analysis Settings
                </Text>
                <Text as="p" variant="bodyMd">
                  Configure how we analyze your store data to find bundle
                  opportunities.
                </Text>

                <BlockStack gap="400">
                  <TextField
                    label="Minimum Support (%)"
                    type="number"
                    value={localSettings.minSupport.toString()}
                    onChange={(value) =>
                      handleSettingChange("minSupport", parseFloat(value) / 100)
                    }
                    suffix="%"
                    helpText="Minimum percentage of orders that must contain both products"
                    autoComplete="off"
                  />

                  <TextField
                    label="Minimum Confidence (%)"
                    type="number"
                    value={(localSettings.minConfidence * 100).toString()}
                    onChange={(value) =>
                      handleSettingChange(
                        "minConfidence",
                        parseFloat(value) / 100,
                      )
                    }
                    suffix="%"
                    helpText="Minimum confidence that products are bought together"
                    autoComplete="off"
                  />

                  <TextField
                    label="Minimum Lift"
                    type="number"
                    value={localSettings.minLift.toString()}
                    onChange={(value) =>
                      handleSettingChange("minLift", parseFloat(value))
                    }
                    helpText="Minimum lift ratio (how much more likely vs random chance)"
                    autoComplete="off"
                  />

                  <TextField
                    label="Analysis Window (Days)"
                    type="number"
                    value={localSettings.analysisWindow.toString()}
                    onChange={(value) =>
                      handleSettingChange("analysisWindow", parseInt(value))
                    }
                    helpText="How many days of order data to analyze"
                    autoComplete="off"
                  />
                </BlockStack>

                <InlineStack gap="300">
                  <Button
                    onClick={saveSettings}
                    loading={fetcher.state === "submitting"}
                  >
                    Save Settings
                  </Button>
                  <Button onClick={refreshAnalysis} variant="secondary">
                    Refresh Analysis
                  </Button>
                </InlineStack>
              </BlockStack>
            </Card>

            {/* Widget Settings */}
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Widget Settings
                </Text>
                <Text as="p" variant="bodyMd">
                  Configure how bundle widgets appear on your store.
                </Text>

                <BlockStack gap="400">
                  <Select
                    label="Widget Placement"
                    options={[
                      { label: "Product Page", value: "product_page" },
                      { label: "Cart Page", value: "cart_page" },
                      { label: "Checkout Page", value: "checkout_page" },
                      { label: "All Pages", value: "all_pages" },
                    ]}
                    value={localSettings.widgetPlacement}
                    onChange={(value) =>
                      handleSettingChange("widgetPlacement", value)
                    }
                    helpText="Where to display bundle recommendations"
                  />

                  <Checkbox
                    label="Auto-refresh Analysis"
                    checked={localSettings.autoRefresh}
                    onChange={(checked) =>
                      handleSettingChange("autoRefresh", checked)
                    }
                  />
                  <Text as="p" variant="bodyMd">
                    Automatically refresh bundle analysis weekly
                  </Text>
                </BlockStack>
              </BlockStack>
            </Card>

            {/* Commission Settings */}
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Commission Settings
                </Text>
                <Text as="p" variant="bodyMd">
                  Configure your commission and billing preferences.
                </Text>

                <BlockStack gap="200">
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodyMd">
                      Commission Rate
                    </Text>
                    <Text as="span" variant="bodyMd">
                      5% (Fixed)
                    </Text>
                  </InlineStack>
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodyMd">
                      Billing Cycle
                    </Text>
                    <Text as="span" variant="bodyMd">
                      Monthly
                    </Text>
                  </InlineStack>
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodyMd">
                      Payment Method
                    </Text>
                    <Text as="span" variant="bodyMd">
                      Shopify Billing
                    </Text>
                  </InlineStack>
                </BlockStack>

                <Text as="p" variant="bodyMd">
                  <strong>Note:</strong> Commission settings are managed by
                  Shopify and cannot be changed here.
                </Text>
              </BlockStack>
            </Card>

            {/* Success/Error Messages */}
            {fetcher.data && (
              <Banner
                title={(fetcher.data as any).success ? "Success" : "Error"}
                tone={(fetcher.data as any).success ? "success" : "critical"}
              >
                {(fetcher.data as any).message || (fetcher.data as any).error}
              </Banner>
            )}
          </BlockStack>
        </Layout.Section>

        {/* Help & Support */}
        <Layout.Section variant="oneThird">
          <BlockStack gap="500">
            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">
                  Help & Support
                </Text>
                <Text as="p" variant="bodyMd">
                  Need help configuring your settings or understanding how
                  BetterBundle works?
                </Text>
                <Button url="mailto:support@betterbundle.com" variant="plain">
                  Contact Support
                </Button>
              </BlockStack>
            </Card>

            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">
                  Recommended Settings
                </Text>
                <Text as="p" variant="bodyMd">
                  For most stores, we recommend:
                </Text>
                <BlockStack gap="200">
                  <Text as="p" variant="bodyMd">
                    • Minimum Support: 1%
                  </Text>
                  <Text as="p" variant="bodyMd">
                    • Minimum Confidence: 10%
                  </Text>
                  <Text as="p" variant="bodyMd">
                    • Minimum Lift: 2.0
                  </Text>
                  <Text as="p" variant="bodyMd">
                    • Analysis Window: 180 days
                  </Text>
                </BlockStack>
              </BlockStack>
            </Card>

            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">
                  Data Privacy
                </Text>
                <Text as="p" variant="bodyMd">
                  We only analyze your order data to find bundle opportunities.
                  We never share your data with third parties.
                </Text>
                <Button url="/privacy" variant="plain">
                  Privacy Policy
                </Button>
              </BlockStack>
            </Card>
          </BlockStack>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
