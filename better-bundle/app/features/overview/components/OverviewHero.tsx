interface OverviewHeroProps {
  shop: {
    shop_domain: string;
  };
}

export function OverviewHero({ shop }: OverviewHeroProps) {
  const shopName = shop.shop_domain.replace(".myshopify.com", "");

  return (
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
            📊 Overview Dashboard
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
          Welcome back, {shopName}!
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
            Here's how your AI recommendations are performing
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
  );
}
