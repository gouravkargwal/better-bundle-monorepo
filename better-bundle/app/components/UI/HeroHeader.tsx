import { ReactNode } from "react";
import { radii, shadows, brand } from "./design.tokens";

type HeroVariant = "gradient" | "subtle" | "white";
type HeroTextTreatment =
  | "default"
  | "inverted"
  | "muted";

interface HeroHeaderProps {
  /** Short label shown as a pill above the title — omit when there is nothing meaningful to say. */
  badge?: string;
  /** Descriptive headline — sell the page's purpose, not its name. */
  title: string;
  /** One-line explanation of what the page helps the merchant do. */
  subtitle: string;
  /** Background treatment for the hero block. */
  variant?: HeroVariant;
  /** Text treatment for the headline. Defaults to the inverse of the background. */
  textTreatment?: HeroTextTreatment;
  /** Alignment for the text block. */
  align?: "center" | "left";
  children?: ReactNode;
}

const gradients: Record<HeroVariant, string> = {
  gradient:
    "linear-gradient(135deg, " +
    brand.indigoStart +
    " 0%, " +
    brand.indigoEnd +
    " 100%)",
  subtle:
    "linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%)",
  white:
    "linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%)",
};

const textGradients: Record<HeroTextTreatment, string> = {
  default: "linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%)",
  inverted: "linear-gradient(135deg, #1E293B 0%, #475569 100%)",
  muted: "linear-gradient(135deg, #475569 0%, #94A3B8 100%)",
};

const textColors: Record<HeroTextTreatment, string> = {
  default: "rgba(255,255,255,0.92)",
  inverted: "#475569",
  muted: "#94A3B8",
};

const decorationVariant: Record<HeroVariant, React.ReactNode> = {
  gradient: (
    <>
      <div
        style={{
          position: "absolute",
          top: "-40px",
          right: "-40px",
          width: "220px",
          height: "220px",
          background:
            "radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)",
          borderRadius: "50%",
          zIndex: 1,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "-60px",
          left: "-60px",
          width: "180px",
          height: "180px",
          background:
            "radial-gradient(circle, rgba(255,255,255,0.06) 0%, transparent 70%)",
          borderRadius: "50%",
          zIndex: 1,
        }}
      />
    </>
  ),
  subtle: (
    <div
      style={{
        position: "absolute",
        bottom: "-30px",
        right: "-30px",
        width: "120px",
        height: "120px",
        background:
          "radial-gradient(circle, rgba(59,130,246,0.06) 0%, transparent 70%)",
        borderRadius: "50%",
        zIndex: 1,
      }}
    />
  ),
  white: null,
};

export function HeroHeader({
  badge,
  title,
  subtitle,
  variant = "gradient",
  textTreatment,
  align = "center",
  children,
}: HeroHeaderProps) {
  const isColor = variant === "gradient";
  const treatment =
    textTreatment ??
    (isColor ? ("default" as const) : ("inverted" as const));

  return (
    <div
      style={{
        padding: "36px 28px",
        background: gradients[variant],
        borderRadius: radii.xl,
        color: isColor ? "white" : "#1E293B",
        textAlign: align,
        position: "relative",
        overflow: "hidden",
        boxShadow: shadows.elevated,
        border: isColor
          ? "1px solid rgba(255, 255, 255, 0.15)"
          : "1px solid #E2E8F0",
      }}
    >
      <div style={{ position: "relative", zIndex: 2 }}>
        {badge && (
          <div
            style={{
              display: "inline-block",
              padding: "5px 11px",
              backgroundColor: isColor
                ? "rgba(255, 255, 255, 0.2)"
                : "rgba(59,130,246,0.12)",
              border: isColor
                ? "1px solid rgba(255, 255, 255, 0.3)"
                : "1px solid rgba(59,130,246,0.25)",
              color: isColor ? "white" : "#1E293B",
              fontWeight: "600",
              borderRadius: radii.sm,
              fontSize: "12px",
              marginBottom: "14px",
              letterSpacing: "0.01em",
            }}
          >
            {badge}
          </div>
        )}

        {/* Main Headline */}
        <h1
          style={{
            fontSize: "clamp(1.5rem, 3vw, 2.25rem)",
            lineHeight: "1.15",
            margin: 0,
            marginBottom: "10px",
            background: textGradients[treatment],
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            fontWeight: "800",
            letterSpacing: "-0.02em",
          }}
        >
          {title}
        </h1>

        {/* Subheadline */}
        <p
          style={{
            maxWidth: align === "left" ? "560px" : "520px",
            margin: 0,
            color: textColors[treatment],
            lineHeight: "1.55",
            fontWeight: "400",
            fontSize: "1rem",
          }}
        >
          {subtitle}
        </p>

        {children}
      </div>

      {decorationVariant[variant]}
    </div>
  );
}
