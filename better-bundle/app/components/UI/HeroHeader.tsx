import { ReactNode } from "react";

interface HeroHeaderProps {
  badge: string;
  title: string;
  subtitle: string;
  gradient: "blue" | "red" | "orange" | "green" | "gray";
  children?: ReactNode;
}

const gradientStyles = {
  blue: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
  red: "linear-gradient(135deg, #DC2626 0%, #B91C1C 100%)",
  orange: "linear-gradient(135deg, #F59E0B 0%, #D97706 100%)",
  green: "linear-gradient(135deg, #10B981 0%, #059669 100%)",
  gray: "linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%)",
};

const textGradients = {
  blue: "linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%)",
  red: "linear-gradient(135deg, #ffffff 0%, #fef2f2 100%)",
  orange: "linear-gradient(135deg, #ffffff 0%, #fef3c7 100%)",
  green: "linear-gradient(135deg, #ffffff 0%, #f0fdf4 100%)",
  gray: "linear-gradient(135deg, #1E293B 0%, #475569 100%)",
};

export function HeroHeader({
  badge,
  title,
  subtitle,
  gradient,
  children,
}: HeroHeaderProps) {
  const isGray = gradient === "gray";

  return (
    <div
      style={{
        padding: "24px 20px",
        background: gradientStyles[gradient],
        borderRadius: "16px",
        color: isGray ? "#1E293B" : "white",
        textAlign: "center",
        position: "relative",
        overflow: "hidden",
        boxShadow:
          "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
        border: isGray
          ? "1px solid #E2E8F0"
          : "1px solid rgba(255, 255, 255, 0.1)",
      }}
    >
      <div style={{ position: "relative", zIndex: 2 }}>
        {/* Hero Badge */}
        <div style={{ marginBottom: "12px" }}>
          <div
            style={{
              display: "inline-block",
              padding: "6px 12px",
              backgroundColor: isGray
                ? "#3B82F615"
                : "rgba(255, 255, 255, 0.2)",
              border: isGray
                ? "1px solid #3B82F630"
                : "1px solid rgba(255, 255, 255, 0.3)",
              color: isGray ? "#1E293B" : "white",
              fontWeight: "600",
              borderRadius: "6px",
              fontSize: "12px",
            }}
          >
            {badge}
          </div>
        </div>

        {/* Main Headline */}
        <div
          style={{
            fontSize: "2rem",
            lineHeight: "1.2",
            marginBottom: "8px",
            background: textGradients[gradient],
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            fontWeight: "bold",
          }}
        >
          {title}
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
              color: isGray ? "#475569" : "rgba(255,255,255,0.95)",
              lineHeight: "1.4",
              fontWeight: "500",
              fontSize: "1rem",
            }}
          >
            {subtitle}
          </div>
        </div>

        {/* Custom content */}
        {children}

        {/* Enhanced Decorative elements - only for colored gradients */}
        {!isGray && (
          <>
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
          </>
        )}
      </div>
    </div>
  );
}
