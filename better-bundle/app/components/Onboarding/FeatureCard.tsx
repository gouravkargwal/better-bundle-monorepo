import { Badge, BlockStack, Card, Icon, Text } from "@shopify/polaris";
import React from "react";
import {
  CashDollarIcon,
  EyeCheckMarkIcon,
  TeamIcon,
  CreditCardIcon,
  StarFilledIcon,
  ClockIcon,
} from "@shopify/polaris-icons";

const FeatureCard = () => {
  const features = [
    {
      icon: CreditCardIcon,
      title: "Pay-As-Performance",
      description:
        "Only pay when you see results! Start with $200 free credits, then pay only for actual revenue generated",
      color: "#F59E0B",
      badge: "Risk-free trial",
      stats: "$200 free credits included",
    },
    {
      icon: CashDollarIcon,
      title: "Increase Revenue",
      description:
        "Boost sales with AI-powered product recommendations that convert visitors into customers",
      color: "#10B981",
      badge: "Up to 30% more sales",
      stats: "Average 25% revenue increase",
    },
    {
      icon: EyeCheckMarkIcon,
      title: "Smart Analytics",
      description:
        "Track performance with detailed attribution metrics and real-time insights",
      color: "#3B82F6",
      badge: "Real-time insights",
      stats: "Track every conversion",
    },
    {
      icon: TeamIcon,
      title: "Better Experience",
      description:
        "Personalized shopping experiences that keep customers coming back",
      color: "#8B5CF6",
      badge: "Higher engagement",
      stats: "40% more engagement",
    },
    {
      icon: StarFilledIcon,
      title: "Easy Setup",
      description:
        "Get started in minutes with our simple, no-code setup process",
      color: "#F59E0B",
      badge: "No coding required",
      stats: "2-minute setup",
    },
    {
      icon: ClockIcon,
      title: "24/7 Optimization",
      description:
        "Automated AI that continuously optimizes your recommendations around the clock",
      color: "#06B6D4",
      badge: "Always improving",
      stats: "Continuous optimization",
    },
  ];
  return (
    <BlockStack gap="400">
      <div style={{ textAlign: "center" }}>
        <Text as="h2" variant="headingLg" fontWeight="bold">
          Why Choose BetterBundle?
        </Text>
        <div style={{ marginTop: "8px" }}>
          <div style={{ color: "#6B7280" }}>
            <Text as="p" variant="bodyLg">
              Everything you need to boost your store's performance
            </Text>
          </div>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
          gap: "16px",
          alignItems: "stretch",
        }}
      >
        {features.map((feature, index) => (
          <div
            key={index}
            style={{
              height: "250px",
              display: "flex",
              flexDirection: "column",
              transition: "all 0.3s ease-in-out",
              cursor: "pointer",
              minHeight: "280px",
              borderRadius: "12px",
              overflow: "hidden",
            }}
            onMouseEnter={(e: React.MouseEvent<HTMLDivElement>) => {
              e.currentTarget.style.transform = "translateY(-4px)";
              e.currentTarget.style.boxShadow = "0 8px 16px rgba(0,0,0,0.12)";
            }}
            onMouseLeave={(e: React.MouseEvent<HTMLDivElement>) => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = "0 2px 4px rgba(0,0,0,0.05)";
            }}
          >
            <Card>
              <div
                style={{
                  padding: "20px",
                  height: "250px",
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: "16px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: "40px",
                      height: "40px",
                      backgroundColor: feature.color + "15",
                      borderRadius: "12px",
                      border: `2px solid ${feature.color}30`,
                    }}
                  >
                    <Icon source={feature.icon} tone="base" />
                  </div>
                  <Badge tone="info" size="small">
                    {feature.badge}
                  </Badge>
                </div>

                <div
                  style={{
                    flex: 1,
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-around",
                  }}
                >
                  <div>
                    <div style={{ marginBottom: "8px" }}>
                      <Text as="h3" variant="headingMd" fontWeight="bold">
                        {feature.title}
                      </Text>
                    </div>
                    <div style={{ color: "#4B5563" }}>
                      <Text as="p" variant="bodyMd">
                        {feature.description}
                      </Text>
                    </div>
                  </div>

                  <div
                    style={{
                      padding: "6px 10px",
                      backgroundColor: feature.color + "10",
                      borderRadius: "6px",
                      border: `1px solid ${feature.color}30`,
                      marginTop: "16px",
                    }}
                  >
                    <Text as="p" variant="bodySm" fontWeight="semibold">
                      {feature.stats}
                    </Text>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        ))}
      </div>
    </BlockStack>
  );
};

export default FeatureCard;
