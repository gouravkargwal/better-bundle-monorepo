import { BlockStack, InlineStack, Text } from "@shopify/polaris";

export const Benefits = () => {
  const benefits = [
    { text: "AI-powered product recommendations", icon: "🤖" },
    { text: "Real-time performance analytics", icon: "📊" },
    { text: "Revenue attribution tracking", icon: "💰" },
    { text: "Customer behavior insights", icon: "👥" },
    { text: "Easy-to-use dashboard", icon: "📱" },
    { text: "24/7 automated optimization", icon: "⚡" },
  ];
  return (
    <div
      style={{
        padding: "32px",
        backgroundColor: "#F8FAFC",
        borderRadius: "16px",
        border: "1px solid #E2E8F0",
      }}
    >
      <BlockStack gap="400">
        <div style={{ textAlign: "center" }}>
          <Text as="h3" variant="headingLg" fontWeight="bold">
            What You'll Get
          </Text>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
            gap: "16px",
            alignItems: "stretch",
          }}
        >
          {benefits.map((benefit, index) => (
            <div
              key={index}
              style={{
                padding: "16px",
                backgroundColor: "white",
                borderRadius: "12px",
                border: "1px solid #E2E8F0",
                boxShadow: "0 2px 4px rgba(0,0,0,0.05)",
                height: "100%",
                display: "flex",
                alignItems: "center",
              }}
            >
              <InlineStack gap="300" blockAlign="center">
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: "40px",
                    height: "40px",
                    backgroundColor: "#10B981",
                    borderRadius: "12px",
                    flexShrink: 0,
                    fontSize: "20px",
                  }}
                >
                  {benefit.icon}
                </div>
                <Text as="p" variant="bodyMd" fontWeight="medium">
                  {benefit.text}
                </Text>
              </InlineStack>
            </div>
          ))}
        </div>
      </BlockStack>
    </div>
  );
};
