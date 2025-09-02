import { useState } from "react";
import {
  Page,
  Layout,
  Card,
  BlockStack,
  Text,
  Tabs,
  Button,
  InlineStack,
  Banner,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { Link, useNavigate } from "@remix-run/react";

export function Dashboard() {
  const [selectedTab, setSelectedTab] = useState(0);
  const navigate = useNavigate();
  const [isStartingAnalysis, setIsStartingAnalysis] = useState(false);

  const handleStartAnalysis = async () => {
    setIsStartingAnalysis(true);
    try {
      // Simple API call to start analysis
      const response = await fetch("/api/analysis/start", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });
      if (response.ok) {
        console.log("Analysis job started successfully");
      } else {
        console.error("Failed to start analysis");
      }
    } catch (error) {
      console.error("Failed to start analysis:", error);
    } finally {
      setIsStartingAnalysis(false);
    }
  };

  const handleSetupWidget = () => {
    navigate("/app/widget");
  };

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

            {/* Analysis Status */}
            {isStartingAnalysis && (
              <Banner tone="info" title="Analysis Status">
                Starting analysis job... This will collect and analyze your
                store data.
              </Banner>
            )}

            {/* Action Buttons */}
            <InlineStack gap="300">
              <Button
                onClick={handleStartAnalysis}
                variant="primary"
                loading={isStartingAnalysis}
                disabled={isStartingAnalysis}
                size="large"
              >
                {isStartingAnalysis
                  ? "Starting Analysis..."
                  : "🚀 Start Analysis"}
              </Button>

              <Button
                onClick={handleSetupWidget}
                variant="secondary"
                size="large"
              >
                🎛️ Setup Widget
              </Button>

              <Link to="/app/billing">
                <Button variant="secondary">💳 Manage Billing & Plans</Button>
              </Link>
            </InlineStack>
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
