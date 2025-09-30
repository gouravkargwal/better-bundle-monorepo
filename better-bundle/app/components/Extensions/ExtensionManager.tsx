import React, { useState } from "react";
import {
  Text,
  BlockStack,
  Icon,
  Badge,
  InlineStack,
  Button,
  Card,
} from "@shopify/polaris";
import { SettingsIcon, ThemeIcon, TeamIcon } from "@shopify/polaris-icons";

interface ExtensionManagerProps {
  extensions: Record<string, any>;
}

interface ExtensionInfo {
  key: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  category: string;
}

export function ExtensionManager({
  extensions: extensionActivity,
}: ExtensionManagerProps) {
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());

  const extensionConfigs: ExtensionInfo[] = [
    {
      key: "venus",
      name: "Customer Account Recommendations",
      description:
        "Shows personalized product recommendations in customer accounts",
      icon: <Icon source={TeamIcon} tone="base" />,
      category: "Customer Experience",
    },
    {
      key: "phoenix",
      name: "Theme App Blocks",
      description: "Adds recommendation widgets to your store pages",
      icon: <Icon source={ThemeIcon} tone="base" />,
      category: "Theme Integration",
    },
    {
      key: "apollo",
      name: "Post-Purchase Upsells",
      description: "Shows additional product recommendations after checkout",
      icon: <Icon source={SettingsIcon} tone="base" />,
      category: "Conversion Optimization",
    },
  ];

  const getStatusBadge = (activity: any) => {
    const isActive = activity?.active || false;

    if (isActive) {
      return (
        <Badge tone="success" size="small">
          Active
        </Badge>
      );
    } else {
      return (
        <Badge tone="critical" size="small">
          Inactive
        </Badge>
      );
    }
  };

  const getTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInMinutes = Math.floor(
      (now.getTime() - date.getTime()) / (1000 * 60),
    );

    if (diffInMinutes < 60) {
      return `${diffInMinutes}m ago`;
    } else if (diffInMinutes < 1440) {
      return `${Math.floor(diffInMinutes / 60)}h ago`;
    } else {
      return `${Math.floor(diffInMinutes / 1440)}d ago`;
    }
  };

  const activeCount = extensionConfigs.filter(
    (ext) => extensionActivity[ext.key]?.active,
  ).length;
  const inactiveCount = extensionConfigs.filter(
    (ext) => !extensionActivity[ext.key]?.active,
  ).length;

  return (
    <BlockStack gap="300">
      {/* Summary Stats - Following dashboard pattern */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "12px",
          alignItems: "stretch",
        }}
      >
        <div
          style={{
            transition: "all 0.2s ease-in-out",
            cursor: "pointer",
            borderRadius: "8px",
            overflow: "hidden",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "translateY(-4px)";
            e.currentTarget.style.boxShadow = "0 12px 30px rgba(0,0,0,0.15)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = "none";
          }}
        >
          <Card>
            <div style={{ minHeight: "100px", padding: "4px" }}>
              <BlockStack gap="200">
                <InlineStack align="space-between" blockAlign="center">
                  <BlockStack gap="100">
                    <Text
                      as="h3"
                      variant="headingSm"
                      tone="subdued"
                      fontWeight="medium"
                    >
                      Active Extensions
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Currently running
                    </Text>
                  </BlockStack>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      minWidth: "40px",
                      minHeight: "40px",
                      padding: "12px",
                      backgroundColor: "#10B98115",
                      borderRadius: "16px",
                      border: "2px solid #10B98130",
                    }}
                  >
                    <Icon source={TeamIcon} tone="base" />
                  </div>
                </InlineStack>

                <div style={{ color: "#10B981" }}>
                  <Text as="p" variant="headingLg" fontWeight="bold">
                    {activeCount}
                  </Text>
                </div>
              </BlockStack>
            </div>
          </Card>
        </div>

        <div
          style={{
            transition: "all 0.2s ease-in-out",
            cursor: "pointer",
            borderRadius: "8px",
            overflow: "hidden",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "translateY(-4px)";
            e.currentTarget.style.boxShadow = "0 12px 30px rgba(0,0,0,0.15)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = "none";
          }}
        >
          <Card>
            <div style={{ minHeight: "100px", padding: "4px" }}>
              <BlockStack gap="200">
                <InlineStack align="space-between" blockAlign="center">
                  <BlockStack gap="100">
                    <Text
                      as="h3"
                      variant="headingSm"
                      tone="subdued"
                      fontWeight="medium"
                    >
                      Inactive Extensions
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Not currently running
                    </Text>
                  </BlockStack>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      minWidth: "40px",
                      minHeight: "40px",
                      padding: "12px",
                      backgroundColor: "#F59E0B15",
                      borderRadius: "16px",
                      border: "2px solid #F59E0B30",
                    }}
                  >
                    <Icon source={SettingsIcon} tone="base" />
                  </div>
                </InlineStack>

                <div style={{ color: "#F59E0B" }}>
                  <Text as="p" variant="headingLg" fontWeight="bold">
                    {inactiveCount}
                  </Text>
                </div>
              </BlockStack>
            </div>
          </Card>
        </div>
      </div>

      {/* Extension Cards - Following dashboard pattern */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "12px",
          alignItems: "stretch",
        }}
      >
        {extensionConfigs.map((extension) => {
          const activity = extensionActivity[extension.key];
          const isActive = activity?.active || false;
          const lastSeen = activity?.last_seen;

          return (
            <div
              key={extension.key}
              style={{
                transition: "all 0.2s ease-in-out",
                cursor: "pointer",
                borderRadius: "8px",
                overflow: "hidden",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-4px)";
                e.currentTarget.style.boxShadow =
                  "0 12px 30px rgba(0,0,0,0.15)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <Card>
                <div style={{ minHeight: "160px", padding: "4px" }}>
                  <BlockStack gap="200">
                    <InlineStack align="space-between" blockAlign="center">
                      <BlockStack gap="100">
                        <Text as="h3" variant="headingSm" fontWeight="bold">
                          {extension.name}
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          {extension.description}
                        </Text>
                      </BlockStack>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          minWidth: "40px",
                          minHeight: "40px",
                          padding: "12px",
                          backgroundColor: isActive ? "#10B98115" : "#F3F4F615",
                          borderRadius: "16px",
                          border: `2px solid ${isActive ? "#10B98130" : "#F3F4F630"}`,
                        }}
                      >
                        {extension.icon}
                      </div>
                    </InlineStack>

                    <InlineStack align="space-between" blockAlign="center">
                      <div>{getStatusBadge(activity)}</div>
                      {isActive && lastSeen && (
                        <Text as="p" variant="bodySm" tone="subdued">
                          {getTimeAgo(lastSeen)}
                        </Text>
                      )}
                    </InlineStack>

                    {/* App Blocks Info */}
                    {isActive &&
                      activity?.app_blocks &&
                      activity.app_blocks.length > 0 && (
                        <div>
                          <Text
                            as="p"
                            variant="bodySm"
                            fontWeight="medium"
                            tone="subdued"
                          >
                            Active locations:
                          </Text>
                          <div
                            style={{
                              display: "flex",
                              flexWrap: "wrap",
                              gap: "4px",
                              marginTop: "4px",
                            }}
                          >
                            {activity.app_blocks
                              .slice(0, 4)
                              .map((block: any, index: number) => (
                                <Badge key={index} size="small" tone="info">
                                  {block.location}
                                </Badge>
                              ))}
                            {activity.app_blocks.length > 4 && (
                              <Button
                                variant="plain"
                                size="micro"
                                onClick={() => {
                                  const newExpanded = new Set(expandedCards);
                                  if (expandedCards.has(extension.key)) {
                                    newExpanded.delete(extension.key);
                                  } else {
                                    newExpanded.add(extension.key);
                                  }
                                  setExpandedCards(newExpanded);
                                }}
                              >
                                {expandedCards.has(extension.key)
                                  ? "Show less"
                                  : `+${activity.app_blocks.length - 4} more`}
                              </Button>
                            )}
                          </div>
                          {expandedCards.has(extension.key) &&
                            activity.app_blocks.length > 4 && (
                              <div
                                style={{
                                  display: "flex",
                                  flexWrap: "wrap",
                                  gap: "4px",
                                  marginTop: "8px",
                                }}
                              >
                                {activity.app_blocks
                                  .slice(4)
                                  .map((block: any, index: number) => (
                                    <Badge
                                      key={index + 4}
                                      size="small"
                                      tone="info"
                                    >
                                      {block.location}
                                    </Badge>
                                  ))}
                              </div>
                            )}
                        </div>
                      )}
                  </BlockStack>
                </div>
              </Card>
            </div>
          );
        })}
      </div>
    </BlockStack>
  );
}
