import { Page, Text, BlockStack, Tabs, InlineStack } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { DateRangePicker } from "../../../components/UI/DateRangePicker";
import { useDashboard } from "../hooks/useDashboard";
import { Outlet, useLocation, useNavigate } from "@remix-run/react";

interface DashboardPageProps {
  startDate: string;
  endDate: string;
  children?: React.ReactNode;
}

export function DashboardPage({
  startDate,
  endDate,
  children,
}: DashboardPageProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { handleDateChange } = useDashboard(null);

  // Determine current tab based on URL
  const getCurrentTab = () => {
    const pathname = location.pathname;
    if (pathname.includes("/performance")) return 1;
    if (pathname.includes("/products")) return 2;
    if (pathname.includes("/activity")) return 3;
    return 0; // default to revenue
  };

  const handleTabChange = (selectedTabIndex: number) => {
    const basePath = "/app/dashboard";
    const params = new URLSearchParams(location.search);
    const queryString = params.toString();
    const query = queryString ? `?${queryString}` : "";

    switch (selectedTabIndex) {
      case 0:
        navigate(`${basePath}/revenue${query}`);
        break;
      case 1:
        navigate(`${basePath}/performance${query}`);
        break;
      case 2:
        navigate(`${basePath}/products${query}`);
        break;
      case 3:
        navigate(`${basePath}/activity${query}`);
        break;
    }
  };

  const tabs = [
    {
      id: "revenue",
      content: "💰 Revenue",
      panelID: "revenue-panel",
    },
    {
      id: "performance",
      content: "📊 Performance",
      panelID: "performance-panel",
    },
    {
      id: "products",
      content: "🏆 Top Products",
      panelID: "products-panel",
    },
    {
      id: "activity",
      content: "⚡ Recent Activity",
      panelID: "activity-panel",
    },
  ];

  const renderTabContent = () => {
    return children || <Outlet />;
  };

  return (
    <Page>
      <TitleBar title="Analytics Dashboard" />
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
                📊 Analytics Dashboard
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
              Performance Analytics
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
                Track your AI recommendations performance and revenue impact
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

        {/* Date Range Picker Section */}
        <InlineStack align="space-between" blockAlign="center">
          <Text as="p" variant="bodySm" tone="subdued">
            Viewing data from {new Date(startDate).toLocaleDateString()} to{" "}
            {new Date(endDate).toLocaleDateString()}
          </Text>
          <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onDateChange={handleDateChange}
          />
        </InlineStack>

        <Tabs tabs={tabs} selected={getCurrentTab()} onSelect={handleTabChange}>
          {renderTabContent()}
        </Tabs>
      </BlockStack>
    </Page>
  );
}
