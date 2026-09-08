// features/overview/components/BillingStatus.tsx
import { Card, Text, BlockStack, Badge, InlineStack } from "@shopify/polaris";
import { surfaces, radii } from "../../../components/UI/design.tokens";

interface BillingStatusProps {
  subscriptionStatus?: string;
  commissionRate?: number;
  isTrialPhase?: boolean;
  totalRevenueGenerated?: number;
  currency?: string;
}

export function BillingStatus({
  subscriptionStatus = "ACTIVE",
  commissionRate = 0.03,
  isTrialPhase = false,
  totalRevenueGenerated = 0,
  currency = "USD",
}: BillingStatusProps) {
  const formatCurrencyValue = (amount: number, currencyCode: string) => {
    const symbol =
      currencyCode === "USD"
        ? "$"
        : currencyCode === "EUR"
          ? "€"
          : currencyCode === "GBP"
            ? "£"
            : currencyCode;
    const numericAmount = Math.abs(amount);
    return `${symbol}${numericAmount.toFixed(2)}`;
  };

  const getStatusBadge = (status: string, isTrial: boolean) => {
    if (isTrial) {
      return (
        <Badge tone="info" size="large">
          Trial Phase
        </Badge>
      );
    }

    switch (status) {
      case "ACTIVE":
        return (
          <Badge tone="success" size="large">
            Active
          </Badge>
        );
      case "SUSPENDED":
        return (
          <Badge tone="warning" size="large">
            Suspended
          </Badge>
        );
      case "CANCELLED":
        return (
          <Badge tone="critical" size="large">
            Cancelled
          </Badge>
        );
      default:
        return (
          <Badge tone="info" size="large">
            {status}
          </Badge>
        );
    }
  };

  const getStatusColor = (status: string, isTrial: boolean) => {
    if (isTrial) return "#0C4A6E";

    switch (status) {
      case "ACTIVE":
        return "#065F46";
      case "SUSPENDED":
        return "#92400E";
      case "CANCELLED":
        return "#991B1B";
      default:
        return "#0C4A6E";
    }
  };

  const getStatusBgColor = (status: string, isTrial: boolean) => {
    if (isTrial) return "#EFF6FF";

    switch (status) {
      case "ACTIVE":
        return "#F0FDF4";
      case "SUSPENDED":
        return "#FEF3C7";
      case "CANCELLED":
        return "#FEF2F2";
      default:
        return "#EFF6FF";
    }
  };

  const getStatusBorderColor = (status: string, isTrial: boolean) => {
    if (isTrial) return "#BAE6FD";

    switch (status) {
      case "ACTIVE":
        return "#BBF7D0";
      case "SUSPENDED":
        return "#FDE68A";
      case "CANCELLED":
        return "#FECACA";
      default:
        return "#BAE6FD";
    }
  };

  return (
    <Card>
      <div style={{ padding: "12px" }}>
        <BlockStack gap="300">
          <div
            style={{
              padding: "12px",
              backgroundColor: getStatusBgColor(
                subscriptionStatus,
                isTrialPhase,
              ),
              borderRadius: radii.md,
              border: `1px solid ${getStatusBorderColor(subscriptionStatus, isTrialPhase)}`,
            }}
          >
            <div
              style={{
                color: getStatusColor(subscriptionStatus, isTrialPhase),
              }}
            >
              <Text as="h3" variant="headingMd" fontWeight="bold">
                Subscription status
              </Text>
            </div>

            <div style={{ marginTop: "12px" }}>
              <InlineStack align="space-between" blockAlign="center">
                <div>
                  <Text as="p" variant="bodyMd" fontWeight="medium">
                    {isTrialPhase ? "Trial Phase" : "Active Subscription"}
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    {isTrialPhase
                      ? "Testing AI recommendations at no cost"
                      : "Commission-based pricing model"}
                  </Text>
                </div>
                {getStatusBadge(subscriptionStatus, isTrialPhase)}
              </InlineStack>
            </div>

            {/* Commission Model Transparency */}
            <div
              style={{
                padding: "12px",
                backgroundColor: "rgba(255,255,255,0.5)",
                borderRadius: radii.md,
                border: "1px solid #E5E7EB",
              }}
            >
              <BlockStack gap="100">
                <Text
                  as="p"
                  variant="bodySm"
                  fontWeight="medium"
                  tone="subdued"
                >
                  Commission model
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  {isTrialPhase
                    ? `No charges during trial • ${(commissionRate * 100).toFixed(1)}% commission after trial`
                    : `${(commissionRate * 100).toFixed(1)}% commission on attributed revenue`}
                </Text>
                {totalRevenueGenerated > 0 && (
                  <Text
                    as="p"
                    variant="bodySm"
                    tone="subdued"
                  >
                    Total generated: {formatCurrencyValue(totalRevenueGenerated, currency)}
                  </Text>
                )}
              </BlockStack>
            </div>
          </div>
        </BlockStack>
      </div>
    </Card>
  );
}
