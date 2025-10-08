import { BlockStack, InlineStack, Text, Badge } from "@shopify/polaris";

export const Benefits = () => {
  const benefits = [
    {
      text: "AI-powered product recommendations",
      icon: "🤖",
      description: "Smart algorithms that learn from your customers",
      highlight: "Core Feature",
    },
    {
      text: "Real-time performance analytics",
      icon: "📊",
      description: "Track revenue impact and conversion rates",
      highlight: "Analytics",
    },
    {
      text: "Revenue attribution tracking",
      icon: "💰",
      description: "See exactly which recommendations drive sales",
      highlight: "Revenue",
    },
    {
      text: "Customer behavior insights",
      icon: "👥",
      description: "Understand shopping patterns and preferences",
      highlight: "Insights",
    },
    {
      text: "Easy-to-use dashboard",
      icon: "📱",
      description: "Intuitive interface for managing your store",
      highlight: "User-Friendly",
    },
    {
      text: "24/7 automated optimization",
      icon: "⚡",
      description: "Continuous improvement without manual work",
      highlight: "Automated",
    },
  ];

  return (
    <div
      style={{
        padding: "clamp(24px, 4vw, 48px) clamp(16px, 3vw, 32px)",
        background: "linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%)",
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
          top: "-50px",
          right: "-50px",
          width: "200px",
          height: "200px",
          background:
            "radial-gradient(circle, rgba(16, 185, 129, 0.1) 0%, transparent 70%)",
          borderRadius: "50%",
          zIndex: 1,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "-30px",
          left: "-30px",
          width: "150px",
          height: "150px",
          background:
            "radial-gradient(circle, rgba(59, 130, 246, 0.1) 0%, transparent 70%)",
          borderRadius: "50%",
          zIndex: 1,
        }}
      />

      <div style={{ position: "relative", zIndex: 2 }}>
        <BlockStack gap="600">
          {/* Header Section */}
          <div style={{ textAlign: "center" }}>
            <div style={{ marginBottom: "16px" }}>
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
                ✨ Complete Solution
              </Badge>
            </div>
            <Text
              as="h2"
              variant="headingXl"
              fontWeight="bold"
              style={{
                marginBottom: "12px",
                background: "linear-gradient(135deg, #1F2937 0%, #374151 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              Everything You Need to Succeed
            </Text>
            <Text
              as="p"
              variant="bodyLg"
              style={{
                color: "#6B7280",
                maxWidth: "600px",
                margin: "0 auto",
                lineHeight: "1.6",
              }}
            >
              Get a complete AI-powered recommendation system with advanced
              analytics, revenue tracking, and automated optimization.
            </Text>
          </div>

          {/* Benefits Grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: "clamp(16px, 3vw, 24px)",
              alignItems: "stretch",
            }}
          >
            {benefits.map((benefit, index) => (
              <div
                key={index}
                style={{
                  padding: "clamp(16px, 3vw, 24px)",
                  backgroundColor: "white",
                  borderRadius: "16px",
                  border: "1px solid #E5E7EB",
                  boxShadow:
                    "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  transition: "all 0.2s ease-in-out",
                  position: "relative",
                  overflow: "hidden",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = "translateY(-2px)";
                  e.currentTarget.style.boxShadow =
                    "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "translateY(0)";
                  e.currentTarget.style.boxShadow =
                    "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)";
                }}
              >
                {/* Highlight Badge */}
                <div style={{ marginBottom: "16px" }}>
                  <Badge
                    size="small"
                    tone="success"
                    style={{
                      backgroundColor: "rgba(16, 185, 129, 0.1)",
                      border: "1px solid rgba(16, 185, 129, 0.2)",
                      color: "#10B981",
                      fontWeight: "600",
                    }}
                  >
                    {benefit.highlight}
                  </Badge>
                </div>

                {/* Icon and Content */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "clamp(12px, 2vw, 16px)",
                    flex: 1,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: "clamp(40px, 6vw, 48px)",
                      height: "clamp(40px, 6vw, 48px)",
                      background:
                        "linear-gradient(135deg, #10B981 0%, #059669 100%)",
                      borderRadius: "14px",
                      flexShrink: 0,
                      fontSize: "clamp(18px, 3vw, 24px)",
                      boxShadow: "0 4px 14px 0 rgba(16, 185, 129, 0.39)",
                    }}
                  >
                    {benefit.icon}
                  </div>

                  <div style={{ flex: 1 }}>
                    <Text
                      as="h4"
                      variant="headingMd"
                      fontWeight="semibold"
                      style={{
                        marginBottom: "8px",
                        color: "#1F2937",
                      }}
                    >
                      {benefit.text}
                    </Text>
                    <Text
                      as="p"
                      variant="bodyMd"
                      style={{
                        color: "#6B7280",
                        lineHeight: "1.5",
                      }}
                    >
                      {benefit.description}
                    </Text>
                  </div>
                </div>

                {/* Decorative accent */}
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    height: "3px",
                    background:
                      "linear-gradient(90deg, #10B981 0%, #059669 100%)",
                  }}
                />
              </div>
            ))}
          </div>
        </BlockStack>
      </div>
    </div>
  );
};
