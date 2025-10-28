// features/overview/components/ROIValueProofSection.tsx
import {
  Card,
  Text,
  BlockStack,
  InlineStack,
  Badge,
  Divider,
} from "@shopify/polaris";
import { getCurrencySymbol } from "../../../utils/currency";

interface ROIValueProofSectionProps {
  totalRevenueGenerated: number;
  currency: string;
  commissionRate: number;
  isTrialPhase: boolean;
}

export function ROIValueProofSection({
  totalRevenueGenerated,
  currency,
  commissionRate,
  isTrialPhase,
}: ROIValueProofSectionProps) {
  const formatCurrencyValue = (amount: number, currencyCode: string) => {
    const symbol = getCurrencySymbol(currencyCode);
    const numericAmount = Math.abs(amount);
    return `${symbol}${numericAmount.toFixed(2)}`;
  };

  const commissionPaid = totalRevenueGenerated * commissionRate;
  const netProfit = totalRevenueGenerated - commissionPaid;
  const roiPercentage =
    commissionPaid > 0 ? (netProfit / commissionPaid) * 100 : 0;

  // Don't show ROI section if there's no revenue data
  if (totalRevenueGenerated === 0) {
    return null;
  }

  // Calculate competitor comparison (assuming $99/month flat rate)
  const competitorMonthlyRate = 99;
  const competitorAnnualRate = competitorMonthlyRate * 12;
  const savingsVsCompetitor = competitorAnnualRate - commissionPaid;

  return (
    <Card>
      <div style={{ padding: "16px" }}>
        <BlockStack gap="300">
          {/* Header */}
          <div>
            <Text as="h3" variant="headingLg" fontWeight="bold">
              💡 Your Investment vs Returns
            </Text>
            <Text as="p" variant="bodyMd" tone="subdued">
              Transparent commission model - you only pay when you earn
            </Text>
          </div>

          {/* ROI Calculator */}
          <div
            style={{
              padding: "16px",
              backgroundColor: "#F0F9FF",
              borderRadius: "10px",
              border: "1px solid #BAE6FD",
            }}
          >
            <BlockStack gap="200">
              <Text as="h4" variant="headingMd" fontWeight="semibold">
                📊 Net Profit Calculator
              </Text>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                  gap: "16px",
                }}
              >
                <div>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Revenue Generated
                  </Text>
                  <Text
                    as="p"
                    variant="headingMd"
                    fontWeight="bold"
                    tone="success"
                  >
                    {formatCurrencyValue(totalRevenueGenerated, currency)}
                  </Text>
                </div>
                <div>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Commission Paid
                  </Text>
                  <Text
                    as="p"
                    variant="headingMd"
                    fontWeight="bold"
                    tone="subdued"
                  >
                    {isTrialPhase
                      ? "Trial (Not charged)"
                      : formatCurrencyValue(commissionPaid, currency)}
                  </Text>
                </div>
                <div>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Net Profit
                  </Text>
                  <Text
                    as="p"
                    variant="headingMd"
                    fontWeight="bold"
                    tone="success"
                  >
                    {isTrialPhase
                      ? formatCurrencyValue(totalRevenueGenerated, currency)
                      : formatCurrencyValue(netProfit, currency)}
                  </Text>
                </div>
                <div>
                  <Text as="p" variant="bodySm" tone="subdued">
                    ROI
                  </Text>
                  <Text
                    as="p"
                    variant="headingMd"
                    fontWeight="bold"
                    tone="success"
                  >
                    {isTrialPhase ? "∞%" : `${roiPercentage.toFixed(0)}%`}
                  </Text>
                </div>
              </div>
            </BlockStack>
          </div>

          {/* Commission Transparency */}
          <div
            style={{
              padding: "16px",
              backgroundColor: "#F0FDF4",
              borderRadius: "10px",
              border: "1px solid #BBF7D0",
            }}
          >
            <BlockStack gap="200">
              <InlineStack align="space-between" blockAlign="center">
                <Text as="h4" variant="headingMd" fontWeight="semibold">
                  🔍 Commission Transparency
                </Text>
                <Badge tone="success" size="large">
                  {(commissionRate * 100).toFixed(1)}% Commission Rate
                </Badge>
              </InlineStack>

              <Text as="p" variant="bodyMd">
                We only charge a small commission on revenue directly attributed
                to our AI recommendations. No upfront costs, no monthly fees -
                you only pay when you earn.
              </Text>
            </BlockStack>
          </div>

          {/* Competitor Comparison */}
          {!isTrialPhase && (
            <div
              style={{
                padding: "16px",
                backgroundColor: "#FEF3C7",
                borderRadius: "10px",
                border: "1px solid #FDE68A",
              }}
            >
              <BlockStack gap="200">
                <Text as="h4" variant="headingMd" fontWeight="semibold">
                  🏆 vs Flat-Rate Competitors
                </Text>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                    gap: "16px",
                  }}
                >
                  <div>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Competitor Annual Cost
                    </Text>
                    <Text
                      as="p"
                      variant="headingMd"
                      fontWeight="bold"
                      tone="critical"
                    >
                      {formatCurrencyValue(competitorAnnualRate, currency)}
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      ($99/month flat rate)
                    </Text>
                  </div>
                  <div>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Better Bundle Cost
                    </Text>
                    <Text
                      as="p"
                      variant="headingMd"
                      fontWeight="bold"
                      tone="success"
                    >
                      {formatCurrencyValue(commissionPaid, currency)}
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      (Commission only)
                    </Text>
                  </div>
                  <div>
                    <Text as="p" variant="bodySm" tone="subdued">
                      You Save
                    </Text>
                    <Text
                      as="p"
                      variant="headingMd"
                      fontWeight="bold"
                      tone="success"
                    >
                      {formatCurrencyValue(savingsVsCompetitor, currency)}
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      (
                      {(
                        (savingsVsCompetitor / competitorAnnualRate) *
                        100
                      ).toFixed(0)}
                      % less)
                    </Text>
                  </div>
                </div>
              </BlockStack>
            </div>
          )}

          {/* Value Proposition */}
          <div
            style={{
              padding: "16px",
              backgroundColor: "#F3E8FF",
              borderRadius: "10px",
              border: "1px solid #C4B5FD",
            }}
          >
            <BlockStack gap="200">
              <Text as="h4" variant="headingMd" fontWeight="semibold">
                ✨ Why Better Bundle Pays for Itself
              </Text>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
                  gap: "16px",
                }}
              >
                <div>
                  <Text as="p" variant="bodyMd" fontWeight="medium">
                    🎯 Performance-Based Pricing
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Only pay when our AI generates revenue for you
                  </Text>
                </div>
                <div>
                  <Text as="p" variant="bodyMd" fontWeight="medium">
                    📈 Proven ROI
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Average stores see 3-5x return on commission investment
                  </Text>
                </div>
                <div>
                  <Text as="p" variant="bodyMd" fontWeight="medium">
                    🚀 No Risk Trial
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Test our AI recommendations risk-free before committing
                  </Text>
                </div>
                <div>
                  <Text as="p" variant="bodyMd" fontWeight="medium">
                    💡 Transparent Costs
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Clear commission structure with no hidden fees
                  </Text>
                </div>
              </div>
            </BlockStack>
          </div>
        </BlockStack>
      </div>
    </Card>
  );
}
