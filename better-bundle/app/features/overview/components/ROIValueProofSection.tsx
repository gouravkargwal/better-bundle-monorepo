import { Card, Text, BlockStack, InlineStack, Badge } from "@shopify/polaris";
import { getCurrencySymbol } from "../../../utils/currency";

interface ROIValueProofSectionProps {
  totalRevenueGenerated: number;
  currency: string;
  monthlyPrice: number;
  isTrialPhase: boolean;
}

export function ROIValueProofSection({
  totalRevenueGenerated,
  currency,
  monthlyPrice,
  isTrialPhase,
}: ROIValueProofSectionProps) {
  const formatCurrencyValue = (amount: number, currencyCode: string) => {
    const symbol = getCurrencySymbol(currencyCode);
    const numericAmount = Math.abs(amount);
    return `${symbol}${numericAmount.toFixed(2)}`;
  };

  const amountPaid = isTrialPhase ? 0 : monthlyPrice;
  const netProfit = totalRevenueGenerated - amountPaid;

  // Don't show ROI section if there's no revenue data
  if (totalRevenueGenerated === 0) {
    return null;
  }

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
              One flat monthly price — no surprises
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
                    Monthly Plan
                  </Text>
                  <Text
                    as="p"
                    variant="headingMd"
                    fontWeight="bold"
                    tone="subdued"
                  >
                    {isTrialPhase
                      ? "Trial (Not charged)"
                      : `${formatCurrencyValue(monthlyPrice, currency)}/mo`}
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
                    {formatCurrencyValue(netProfit, currency)}
                  </Text>
                </div>
              </div>
            </BlockStack>
          </div>

          {/* Pricing Transparency */}
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
                  🔍 Simple, Transparent Pricing
                </Text>
                <Badge tone="success" size="large">
                  {`${formatCurrencyValue(monthlyPrice, currency)}/mo flat`}
                </Badge>
              </InlineStack>

              <Text as="p" variant="bodyMd">
                One flat monthly price, no matter how much revenue our AI
                recommendations drive for you. No commission, no usage caps,
                no surprises.
              </Text>
            </BlockStack>
          </div>

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
                ✨ Why BetterBundle Pays for Itself
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
                    💵 Predictable Pricing
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    One flat monthly price — never scales with your sales
                  </Text>
                </div>
                <div>
                  <Text as="p" variant="bodyMd" fontWeight="medium">
                    📈 Proven ROI
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Average stores see 3-5x return on their subscription cost
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
                    No hidden fees, no usage caps, no commission math
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
