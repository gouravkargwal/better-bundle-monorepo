// features/onboarding/components/OnboardingHero.tsx
import { Button, Text, Badge } from "@shopify/polaris";
import { ArrowRightIcon } from "@shopify/polaris-icons";
import type { OnboardingError } from "../services/onboarding.types";
import { Form } from "@remix-run/react";

interface OnboardingHeroProps {
  isLoading: boolean;
  error?: OnboardingError;
  pricingTier?: {
    symbol: string;
    threshold_amount: number;
  } | null;
}

export function OnboardingHero({
  isLoading,
  error,
  pricingTier,
}: OnboardingHeroProps) {
  return (
    <div
      style={{
        padding: "40px 32px",
        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        borderRadius: "24px",
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
        {/* Hero Badge */}
        <div style={{ marginBottom: "16px" }}>
          <Badge
            size="large"
            tone="info"
            style={{
              backgroundColor: "rgba(255, 255, 255, 0.2)",
              border: "1px solid rgba(255, 255, 255, 0.3)",
              color: "white",
              fontWeight: "600",
            }}
          >
            ✨ New AI-Powered Solution
          </Badge>
        </div>

        {/* Main Headline */}
        <Text
          as="h1"
          variant="heading2xl"
          fontWeight="bold"
          style={{
            fontSize: "3rem",
            lineHeight: "1.1",
            marginBottom: "16px",
            background: "linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
          }}
        >
          Welcome to BetterBundle!
        </Text>

        {/* Subheadline */}
        <div
          style={{
            marginBottom: "20px",
            maxWidth: "600px",
            margin: "0 auto 20px",
          }}
        >
          <Text
            as="p"
            variant="headingLg"
            style={{
              color: "rgba(255,255,255,0.95)",
              lineHeight: "1.6",
              fontWeight: "500",
            }}
          >
            Transform your store with AI-powered product recommendations that
            boost revenue by up to 30%
          </Text>
        </div>

        {/* Key Benefits Row */}
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: "24px",
            marginBottom: "24px",
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div
              style={{
                width: "8px",
                height: "8px",
                backgroundColor: "#10B981",
                borderRadius: "50%",
              }}
            />
            <Text
              as="span"
              variant="bodyLg"
              style={{ color: "rgba(255,255,255,0.9)" }}
            >
              {pricingTier && pricingTier.symbol
                ? `${pricingTier.symbol}${Math.round(pricingTier.threshold_amount).toLocaleString()} Free Credits`
                : "$200 Free Credits"}
            </Text>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div
              style={{
                width: "8px",
                height: "8px",
                backgroundColor: "#10B981",
                borderRadius: "50%",
              }}
            />
            <Text
              as="span"
              variant="bodyLg"
              style={{ color: "rgba(255,255,255,0.9)" }}
            >
              No Setup Fees
            </Text>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div
              style={{
                width: "8px",
                height: "8px",
                backgroundColor: "#10B981",
                borderRadius: "50%",
              }}
            />
            <Text
              as="span"
              variant="bodyLg"
              style={{ color: "rgba(255,255,255,0.9)" }}
            >
              2-Minute Setup
            </Text>
          </div>
        </div>

        {/* Pay-As-Performance Highlight */}
        <div
          style={{
            marginBottom: "24px",
            padding: "20px",
            backgroundColor: "rgba(255,255,255,0.12)",
            borderRadius: "16px",
            border: "1px solid rgba(255,255,255,0.2)",
            backdropFilter: "blur(10px)",
            maxWidth: "500px",
            margin: "0 auto 24px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "12px",
              marginBottom: "16px",
            }}
          >
            <div
              style={{
                width: "32px",
                height: "32px",
                backgroundColor: "rgba(16, 185, 129, 0.2)",
                borderRadius: "8px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Text as="span" variant="bodyLg" fontWeight="bold">
                💳
              </Text>
            </div>
            <Text as="h3" variant="headingLg" fontWeight="bold">
              Pay-As-Performance Model
            </Text>
          </div>

          <Text
            as="p"
            variant="bodyLg"
            style={{
              color: "rgba(255,255,255,0.95)",
              lineHeight: "1.5",
              marginBottom: "20px",
            }}
          >
            Only pay when you see results • No upfront costs • Risk-free trial
          </Text>

          <Badge
            size="large"
            tone="success"
            style={{
              backgroundColor: "rgba(16, 185, 129, 0.2)",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              color: "#10B981",
              fontWeight: "600",
            }}
          >
            🎯 Guaranteed Results
          </Badge>
        </div>

        {/* Call to Action Button */}
        <div>
          <Form method="post" name="onboarding-form">
            <Button
              submit
              variant="primary"
              size="large"
              icon={isLoading ? undefined : ArrowRightIcon}
              loading={isLoading}
              disabled={isLoading}
              style={{
                padding: "16px 32px",
                fontSize: "18px",
                fontWeight: "600",
                borderRadius: "12px",
                boxShadow: "0 4px 14px 0 rgba(0, 118, 255, 0.39)",
                border: "none",
              }}
            >
              {isLoading
                ? "Setting up your store..."
                : "Start Your Free Trial Now"}
            </Button>
          </Form>
          <div style={{ marginTop: "12px" }}>
            <Text
              as="p"
              variant="bodyMd"
              style={{
                color: "rgba(255,255,255,0.8)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "16px",
                flexWrap: "wrap",
              }}
            >
              <span>⚡ Setup in 2 minutes</span>
              <span>•</span>
              <span>🔒 No coding required</span>
              <span>•</span>
              <span>📈 Results in 24 hours</span>
            </Text>
          </div>
        </div>
      </div>
    </div>
  );
}
