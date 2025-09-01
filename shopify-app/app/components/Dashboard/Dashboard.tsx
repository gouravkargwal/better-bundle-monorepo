import { useState } from "react";
import { Page, Layout, Card, BlockStack, Text, Tabs } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";

export function Dashboard() {
  const [selectedTab, setSelectedTab] = useState(0);

  const tabs = [
    {
      id: "overview",
      content: "Overview",
      accessibilityLabel: "Business overview",
      panelID: "overview-panel",
    },
    {
      id: "bundles",
      content: "Product Bundles",
      accessibilityLabel: "Active bundle recommendations",
      panelID: "bundles-panel",
    },
    {
      id: "performance",
      content: "Performance",
      accessibilityLabel: "Sales and conversion metrics",
      panelID: "performance-panel",
    },
    {
      id: "insights",
      content: "Insights",
      accessibilityLabel: "Actionable business insights",
      panelID: "insights-panel",
    },
  ];

  const renderOverview = () => (
    <Layout>
      <Layout.Section>
        <Card>
          <BlockStack gap="500">
            <Text as="h2" variant="headingMd">
              🚀 Welcome to BetterBundle
            </Text>
            <Text as="p" variant="bodyMd">
              Boost your sales with AI-powered product bundle recommendations.
              We analyze your customer behavior to suggest products that sell
              better together.
            </Text>
          </BlockStack>
        </Card>
      </Layout.Section>
    </Layout>
  );

  const renderTabContent = () => {
    switch (selectedTab) {
      case 0:
        return renderOverview();
      default:
        return renderOverview();
    }
  };

  return (
    <Page>
      <TitleBar title="Dashboard" />
      <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
        {renderTabContent()}
      </Tabs>
    </Page>
  );
}
