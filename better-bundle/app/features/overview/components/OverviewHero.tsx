import { formatCurrency } from "app/utils/currency";

interface OverviewHeroProps {
  subscriptionStatus?: string;
  totalRevenueGenerated?: number;
  currency?: string;
}

export function OverviewHero({
  subscriptionStatus,
  totalRevenueGenerated,
  currency,
}: OverviewHeroProps) {
  const getStatusBadge = () => {
    switch (subscriptionStatus) {
      case "TRIAL":
        return {
          text: "Trial",
          color: "#F59E0B",
          bgColor: "rgba(245, 158, 11, 0.2)",
        };
      case "ACTIVE":
        return {
          text: "Active",
          color: "#10B981",
          bgColor: "rgba(16, 185, 129, 0.2)",
        };
      case "SUSPENDED":
        return {
          text: "Suspended",
          color: "#EF4444",
          bgColor: "rgba(239, 68, 68, 0.2)",
        };
      default:
        return {
          text: "Active",
          color: "#10B981",
          bgColor: "rgba(16, 185, 129, 0.2)",
        };
    }
  };

  const statusBadge = getStatusBadge();

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
        {/* App Name and Status Badge */}
        <div style={{ marginBottom: "16px" }}>
          <div
            style={{
              display: "inline-block",
              padding: "8px 16px",
              backgroundColor: statusBadge.bgColor,
              border: `1px solid ${statusBadge.color}40`,
              color: statusBadge.color,
              fontWeight: "600",
              borderRadius: "8px",
              fontSize: "14px",
              marginBottom: "12px",
            }}
          >
            🚀 Better Bundle • {statusBadge.text}
          </div>
        </div>

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

        {/* Value Communication */}
        {totalRevenueGenerated && totalRevenueGenerated > 0 && (
          <div
            style={{
              marginTop: "20px",
              padding: "16px 24px",
              backgroundColor: "rgba(255, 255, 255, 0.1)",
              borderRadius: "12px",
              border: "1px solid rgba(255, 255, 255, 0.2)",
              backdropFilter: "blur(10px)",
            }}
          >
            <div
              style={{
                fontSize: "1.5rem",
                fontWeight: "bold",
                marginBottom: "4px",
                color: "#10B981",
              }}
            >
              {formatCurrency(totalRevenueGenerated, currency || "USD", {
                showSymbol: true,
              })}
              Generated
            </div>
            <div
              style={{
                fontSize: "0.9rem",
                color: "rgba(255,255,255,0.8)",
              }}
            >
              Revenue attributed to AI recommendations
            </div>
          </div>
        )}

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
