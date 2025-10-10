import { Badge, BlockStack, Icon, Text } from "@shopify/polaris";
import React from "react";
import {
  CashDollarIcon,
  EyeCheckMarkIcon,
  TeamIcon,
  CreditCardIcon,
  StarFilledIcon,
  ClockIcon,
} from "@shopify/polaris-icons";

interface FeatureCardProps {
  pricingTier?: {
    symbol: string;
    threshold_amount: number;
  } | null;
}

const FeatureCard = ({ pricingTier }: FeatureCardProps) => {
  const features = [
    {
      icon: CreditCardIcon,
      title: "Pay-As-Performance",
      description: `Only pay when you see results! Start with ${pricingTier && pricingTier.symbol ? `${pricingTier.symbol}${Math.round(pricingTier.threshold_amount).toLocaleString()}` : "$200"} free credits, then pay only for actual revenue generated`,
      color: "#F59E0B",
      badge: "Risk-free trial",
      stats: `${pricingTier && pricingTier.symbol ? `${pricingTier.symbol}${Math.round(pricingTier.threshold_amount).toLocaleString()}` : "$200"} free credits included`,
      highlight: "No upfront costs",
      gradient: "linear-gradient(135deg, #F59E0B 0%, #D97706 100%)",
    },
    {
      icon: CashDollarIcon,
      title: "Increase Revenue",
      description:
        "Boost sales with AI-powered product recommendations that convert visitors into customers",
      color: "#10B981",
      badge: "Up to 30% more sales",
      stats: "Average 25% revenue increase",
      highlight: "Proven results",
      gradient: "linear-gradient(135deg, #10B981 0%, #059669 100%)",
    },
    {
      icon: EyeCheckMarkIcon,
      title: "Smart Analytics",
      description:
        "Track performance with detailed attribution metrics and real-time insights",
      color: "#3B82F6",
      badge: "Real-time insights",
      stats: "Track every conversion",
      highlight: "Data-driven",
      gradient: "linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)",
    },
    {
      icon: TeamIcon,
      title: "Better Experience",
      description:
        "Personalized shopping experiences that keep customers coming back",
      color: "#8B5CF6",
      badge: "Higher engagement",
      stats: "40% more engagement",
      highlight: "Customer-focused",
      gradient: "linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%)",
    },
    {
      icon: StarFilledIcon,
      title: "Easy Setup",
      description:
        "Get started in minutes with our simple, no-code setup process",
      color: "#F59E0B",
      badge: "No coding required",
      stats: "2-minute setup",
      highlight: "Quick start",
      gradient: "linear-gradient(135deg, #F59E0B 0%, #D97706 100%)",
    },
    {
      icon: ClockIcon,
      title: "24/7 Optimization",
      description:
        "Automated AI that continuously optimizes your recommendations around the clock",
      color: "#06B6D4",
      badge: "Always improving",
      stats: "Continuous optimization",
      highlight: "Always-on",
      gradient: "linear-gradient(135deg, #06B6D4 0%, #0891B2 100%)",
    },
  ];

  return (
    <div
      style={{
        padding: "clamp(24px, 4vw, 48px) clamp(16px, 3vw, 32px)",
        background: "linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%)",
        borderRadius: "20px",
        border: "1px solid #E2E8F0",
        boxShadow:
          "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Background decorative elements */}
      <div
        style={{
          position: "absolute",
          top: "-100px",
          right: "-100px",
          width: "300px",
          height: "300px",
          background:
            "radial-gradient(circle, rgba(16, 185, 129, 0.05) 0%, transparent 70%)",
          borderRadius: "50%",
          zIndex: 1,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "-80px",
          left: "-80px",
          width: "250px",
          height: "250px",
          background:
            "radial-gradient(circle, rgba(59, 130, 246, 0.05) 0%, transparent 70%)",
          borderRadius: "50%",
          zIndex: 1,
        }}
      />

      <div style={{ position: "relative", zIndex: 2 }}>
        <BlockStack gap="400">
          {/* Header Section */}
          <div style={{ textAlign: "center" }}>
            <div style={{ marginBottom: "12px" }}>
              <Badge
                size="large"
                tone="info"
                style={{
                  backgroundColor: "rgba(16, 185, 129, 0.1)",
                  border: "1px solid rgba(16, 185, 129, 0.2)",
                  color: "#10B981",
                  fontWeight: "600",
                }}
              >
                🚀 Why Choose BetterBundle?
              </Badge>
            </div>
            <Text
              as="h2"
              variant="headingLg"
              fontWeight="bold"
              style={{
                marginBottom: "8px",
                background: "linear-gradient(135deg, #1F2937 0%, #374151 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              Powerful Features That Drive Results
            </Text>
            <Text
              as="p"
              variant="bodyMd"
              style={{
                color: "#6B7280",
                maxWidth: "500px",
                margin: "0 auto",
                lineHeight: "1.5",
              }}
            >
              Everything you need to boost your store's performance with
              AI-powered recommendations and advanced analytics.
            </Text>
          </div>

          {/* Features Grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: "clamp(16px, 3vw, 24px)",
              alignItems: "stretch",
            }}
          >
            {features.map((feature, index) => (
              <div
                key={index}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  transition: "all 0.3s ease-in-out",
                  cursor: "pointer",
                  borderRadius: "16px",
                  overflow: "hidden",
                  position: "relative",
                  boxShadow:
                    "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
                }}
                onMouseEnter={(e: React.MouseEvent<HTMLDivElement>) => {
                  e.currentTarget.style.transform = "translateY(-6px)";
                  e.currentTarget.style.boxShadow =
                    "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)";
                }}
                onMouseLeave={(e: React.MouseEvent<HTMLDivElement>) => {
                  e.currentTarget.style.transform = "translateY(0)";
                  e.currentTarget.style.boxShadow =
                    "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)";
                }}
              >
                <div
                  style={{
                    backgroundColor: "white",
                    borderRadius: "16px",
                    border: "1px solid #E5E7EB",
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <div
                    style={{
                      padding: "clamp(16px, 3vw, 20px)",
                      display: "flex",
                      flexDirection: "column",
                      height: "100%",
                      position: "relative",
                      flex: 1,
                    }}
                  >
                    {/* Decorative accent */}
                    <div
                      style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        right: 0,
                        height: "4px",
                        background: feature.gradient,
                      }}
                    />

                    {/* Header with icon and badge */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        justifyContent: "space-between",
                        marginBottom: "16px",
                        marginTop: "4px",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          width: "clamp(40px, 6vw, 48px)",
                          height: "clamp(40px, 6vw, 48px)",
                          background: feature.gradient,
                          borderRadius: "14px",
                          boxShadow: `0 4px 14px 0 ${feature.color}39`,
                          flexShrink: 0,
                        }}
                      >
                        <Icon source={feature.icon} tone="base" />
                      </div>
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "8px",
                          alignItems: "flex-end",
                        }}
                      >
                        <Badge
                          tone="success"
                          size="small"
                          style={{
                            backgroundColor: `${feature.color}15`,
                            border: `1px solid ${feature.color}30`,
                            color: feature.color,
                            fontWeight: "600",
                          }}
                        >
                          {feature.badge}
                        </Badge>
                        <Badge
                          tone="info"
                          size="small"
                          style={{
                            backgroundColor: `${feature.color}10`,
                            border: `1px solid ${feature.color}20`,
                            color: feature.color,
                            fontWeight: "500",
                          }}
                        >
                          {feature.highlight}
                        </Badge>
                      </div>
                    </div>

                    {/* Content */}
                    <div
                      style={{
                        flex: 1,
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "space-between",
                      }}
                    >
                      <div>
                        <Text
                          as="h3"
                          variant="headingMd"
                          fontWeight="bold"
                          style={{
                            marginBottom: "8px",
                            color: "#1F2937",
                            lineHeight: "1.3",
                          }}
                        >
                          {feature.title}
                        </Text>
                        <Text
                          as="p"
                          variant="bodyMd"
                          style={{
                            color: "#6B7280",
                            lineHeight: "1.5",
                            marginBottom: "16px",
                          }}
                        >
                          {feature.description}
                        </Text>
                      </div>

                      {/* Stats section */}
                      <div
                        style={{
                          padding: "clamp(10px, 2.5vw, 12px)",
                          background: `${feature.color}08`,
                          borderRadius: "10px",
                          border: `1px solid ${feature.color}20`,
                          marginTop: "auto",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                          }}
                        >
                          <div
                            style={{
                              width: "8px",
                              height: "8px",
                              backgroundColor: feature.color,
                              borderRadius: "50%",
                            }}
                          />
                          <Text
                            as="p"
                            variant="bodyMd"
                            fontWeight="semibold"
                            style={{ color: feature.color }}
                          >
                            {feature.stats}
                          </Text>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </BlockStack>
      </div>
    </div>
  );
};

export default FeatureCard;
