import { formatCurrency } from "app/utils/currency";

interface OverviewHeroProps {
  totalRevenueGenerated?: number;
  currency?: string;
}

export function OverviewHero({
  totalRevenueGenerated,
  currency,
}: OverviewHeroProps) {
  return (
    <div
      style={{
        padding: "32px 24px",
        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        borderRadius: "20px",
        color: "white",
        textAlign: "center",
        position: "relative",
        overflow: "hidden",
        boxShadow:
          "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
        border: "1px solid rgba(255, 255, 255, 0.1)",
      }}
    >
      <div style={{ position: "relative", zIndex: 2 }}>
        {/* Main Headline */}
        <div
          style={{
            fontSize: "2.5rem",
            lineHeight: "1.1",
            marginBottom: "12px",
            background: "linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            fontWeight: "bold",
          }}
        >
          Better Bundle
        </div>

        {/* Tagline */}
        <div
          style={{
            marginBottom: "16px",
            maxWidth: "600px",
            margin: "0 auto 16px",
          }}
        >
          <div
            style={{
              color: "rgba(255,255,255,0.95)",
              lineHeight: "1.5",
              fontWeight: "600",
              fontSize: "1.1rem",
            }}
          >
            AI-powered recommendations that pay for themselves
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
