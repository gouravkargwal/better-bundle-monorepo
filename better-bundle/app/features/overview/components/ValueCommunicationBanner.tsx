// features/overview/components/ValueCommunicationBanner.tsx
import { Card, Text, BlockStack, Button, Badge } from "@shopify/polaris";
import { getCurrencySymbol } from "../../../utils/currency";

interface ValueCommunicationBannerProps {
  subscriptionStatus: string;
  totalRevenueGenerated: number;
  currency: string;
  commissionRate: number;
  isTrialPhase: boolean;
}

export function ValueCommunicationBanner({
  subscriptionStatus,
  totalRevenueGenerated,
  currency,
  commissionRate,
  isTrialPhase,
}: ValueCommunicationBannerProps) {
  const formatCurrencyValue = (amount: number, currencyCode: string) => {
    const symbol = getCurrencySymbol(currencyCode);
    const numericAmount = Math.abs(amount);
    return `${symbol}${numericAmount.toFixed(2)}`;
  };

  const commissionPaid = totalRevenueGenerated * commissionRate;
  const netProfit = totalRevenueGenerated - commissionPaid;

  const getBannerContent = () => {
    switch (subscriptionStatus) {
      case "TRIAL":
        return {
          title: "🚀 Trial Performance",
          subtitle: `You've generated ${formatCurrencyValue(totalRevenueGenerated, currency)} during your trial`,
          description:
            "Commission tracked but not charged yet. Upgrade to start earning with our AI recommendations!",
          ctaText: "Upgrade Now",
          ctaAction: () => (window.location.href = "/app/billing"),
          bgColor: "#FEF3C7",
          borderColor: "#F59E0B",
          textColor: "#92400E",
        };
      case "ACTIVE":
        if (totalRevenueGenerated > 0) {
          return {
            title: "💰 ROI Success",
            subtitle: `Net profit: ${formatCurrencyValue(netProfit, currency)} from ${formatCurrencyValue(totalRevenueGenerated, currency)} generated`,
            description: `You paid only ${formatCurrencyValue(commissionPaid, currency)} (${(commissionRate * 100).toFixed(1)}% commission) for ${formatCurrencyValue(totalRevenueGenerated, currency)} in revenue`,
            ctaText: "View Analytics",
            ctaAction: () => (window.location.href = "/app/analytics"),
            bgColor: "#D1FAE5",
            borderColor: "#10B981",
            textColor: "#065F46",
          };
        } else {
          return {
            title: "🚀 Ready to Earn",
            subtitle:
              "Your AI recommendations are active and ready to generate revenue",
            description:
              "Once customers start purchasing through our recommendations, you'll see your ROI metrics here",
            ctaText: "View Analytics",
            ctaAction: () => (window.location.href = "/app/analytics"),
            bgColor: "#EFF6FF",
            borderColor: "#3B82F6",
            textColor: "#1E40AF",
          };
        }
      case "SUSPENDED":
        return {
          title: "⚠️ Service Suspended",
          subtitle: `You generated ${formatCurrencyValue(totalRevenueGenerated, currency)} before suspension`,
          description:
            "Reactivate your subscription to continue earning from AI recommendations",
          ctaText: "Reactivate",
          ctaAction: () => (window.location.href = "/app/billing"),
          bgColor: "#FEE2E2",
          borderColor: "#EF4444",
          textColor: "#991B1B",
        };
      default:
        return {
          title: "📊 Performance Overview",
          subtitle: `Revenue generated: ${formatCurrencyValue(totalRevenueGenerated, currency)}`,
          description: "AI recommendations are working to increase your sales",
          ctaText: "Learn More",
          ctaAction: () => (window.location.href = "/app/help"),
          bgColor: "#EFF6FF",
          borderColor: "#3B82F6",
          textColor: "#1E40AF",
        };
    }
  };

  const bannerContent = getBannerContent();

  return (
    <Card>
      <div style={{ padding: "16px" }}>
        <div
          style={{
            padding: "16px",
            backgroundColor: bannerContent.bgColor,
            borderRadius: "10px",
            border: `2px solid ${bannerContent.borderColor}`,
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* Status Badge */}
          <div style={{ marginBottom: "12px" }}>
            <Badge
              tone={
                subscriptionStatus === "ACTIVE"
                  ? "success"
                  : subscriptionStatus === "TRIAL"
                    ? "warning"
                    : "critical"
              }
              size="large"
            >
              {subscriptionStatus === "TRIAL"
                ? "Trial"
                : subscriptionStatus === "ACTIVE"
                  ? "Active"
                  : "Suspended"}
            </Badge>
          </div>

          {/* Main Content */}
          <BlockStack gap="200">
            <div style={{ color: bannerContent.textColor }}>
              <Text as="h3" variant="headingLg" fontWeight="bold">
                {bannerContent.title}
              </Text>
            </div>

            <div style={{ color: bannerContent.textColor }}>
              <Text as="p" variant="headingMd" fontWeight="semibold">
                {bannerContent.subtitle}
              </Text>
            </div>

            <div style={{ color: bannerContent.textColor, opacity: 0.8 }}>
              <Text as="p" variant="bodyMd">
                {bannerContent.description}
              </Text>
            </div>

            {/* CTA Button */}
            <div style={{ marginTop: "12px" }}>
              <Button
                variant="primary"
                onClick={bannerContent.ctaAction}
                size="large"
              >
                {bannerContent.ctaText}
              </Button>
            </div>
          </BlockStack>

          {/* Decorative Elements */}
          <div
            style={{
              position: "absolute",
              top: "-20px",
              right: "-20px",
              width: "80px",
              height: "80px",
              background: `radial-gradient(circle, ${bannerContent.borderColor}20 0%, transparent 70%)`,
              borderRadius: "50%",
              zIndex: 1,
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: "-15px",
              left: "-15px",
              width: "60px",
              height: "60px",
              background: `radial-gradient(circle, ${bannerContent.borderColor}15 0%, transparent 70%)`,
              borderRadius: "50%",
              zIndex: 1,
            }}
          />
        </div>
      </div>
    </Card>
  );
}
