import React from "react";
import { Text, BlockStack, Icon } from "@shopify/polaris";
import { SettingsIcon, ThemeIcon, TeamIcon } from "@shopify/polaris-icons";

export function ExtensionManager() {
  const extensions = [
    {
      key: "venus",
      name: "Account Recommendations",
      description:
        "Shows personalized product recommendations in customer accounts",
      icon: <Icon source={TeamIcon} />,
      activationGuide:
        "This extension works automatically when customers log into their accounts. No setup required - it's enabled by default.",
    },
    {
      key: "phoenix",
      name: "Theme Widgets",
      description: "Adds recommendation widgets to your store pages",
      icon: <Icon source={ThemeIcon} />,
      activationGuide:
        "Go to Online Store > Themes > Customize > Add section > BetterBundle widgets. This requires manual installation in your theme.",
    },
    {
      key: "apollo",
      name: "Post-Purchase Upsells",
      description: "Shows additional product recommendations after checkout",
      icon: <Icon source={SettingsIcon} />,
      activationGuide:
        "This extension works automatically after customers complete their purchase. No setup required - it's enabled by default.",
    },
  ];

  return (
    <BlockStack gap="500">
      {/* Extension Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "16px",
        }}
      >
        {extensions.map((extension) => (
          <div
            key={extension.key}
            style={{
              backgroundColor: "white",
              borderRadius: "12px",
              border: "1px solid #E1E3E5",
              padding: "20px",
              transition: "all 0.2s ease-in-out",
              cursor: "pointer",
              minHeight: "140px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = "translateY(-2px)";
              e.currentTarget.style.boxShadow = "0 8px 25px rgba(0,0,0,0.1)";
              e.currentTarget.style.borderColor = "#008060";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = "none";
              e.currentTarget.style.borderColor = "#E1E3E5";
            }}
          >
            {/* Header */}
            <div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  marginBottom: "8px",
                }}
              >
                <div
                  style={{
                    width: "32px",
                    height: "32px",
                    borderRadius: "8px",
                    backgroundColor: "#F0FDF4",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    border: "1px solid #A7F3D0",
                  }}
                >
                  {extension.icon}
                </div>
                <div style={{ flex: 1 }}>
                  <Text as="h3" variant="headingSm" fontWeight="bold">
                    {extension.name}
                  </Text>
                </div>
              </div>

              <div style={{ marginBottom: "12px" }}>
                <Text as="p" variant="bodySm" tone="subdued">
                  {extension.description}
                </Text>
              </div>

              <div
                style={{
                  padding: "8px 12px",
                  backgroundColor: "#F8FAFC",
                  borderRadius: "6px",
                  border: "1px solid #E2E8F0",
                  marginBottom: "12px",
                }}
              >
                <Text as="p" variant="bodySm" tone="subdued">
                  {extension.activationGuide}
                </Text>
              </div>
            </div>

            {/* Status Indicator */}
            <div>
              <div
                style={{
                  padding: "8px 12px",
                  backgroundColor: "#F0F9FF",
                  borderRadius: "6px",
                  border: "1px solid #BAE6FD",
                  textAlign: "center",
                }}
              >
                <div style={{ color: "#0369A1" }}>
                  <Text as="p" variant="bodySm" fontWeight="medium">
                    ℹ️ Information
                  </Text>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </BlockStack>
  );
}
