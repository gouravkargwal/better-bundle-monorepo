import {
  Banner,
  BlockStack,
  Button,
  Card,
  InlineStack,
  Text,
  Icon,
  ProgressBar,
  Badge,
} from "@shopify/polaris";
import {
  CreditCardIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  StarFilledIcon,
} from "@shopify/polaris-icons";

interface BillingSetupProps {
  billingData: {
    billing_plan: {
      id: string;
      name: string;
      type: string;
      status: string;
      configuration: any;
      currency: string;
      trial_status: {
        is_trial_active?: boolean;
        trial_threshold?: number;
        trial_revenue?: number;
        remaining_revenue: number;
        trial_progress: number;
      };
    };
  };
  onSetupBilling: () => void;
  isLoading?: boolean;
}

export function BillingSetup({
  billingData,
  onSetupBilling,
  isLoading = false,
}: BillingSetupProps) {
  const plan = billingData.billing_plan;
  const trialStatus = plan.trial_status;
  const config = plan.configuration || {};

  // Check if trial is completed and billing setup is required
  const isTrialCompleted =
    !trialStatus.is_trial_active && config.trial_completed_at;
  const needsBillingSetup =
    config.subscription_required && !config.subscription_id;
  const hasActiveSubscription =
    config.subscription_id && config.subscription_status === "ACTIVE";

  // Safe trial status values
  const safeTrialStatus = {
    is_trial_active: trialStatus?.is_trial_active || false,
    trial_threshold: Number(trialStatus?.trial_threshold) || 0,
    trial_revenue: Number(trialStatus?.trial_revenue) || 0,
    remaining_revenue: Math.max(
      0,
      (Number(trialStatus?.trial_threshold) || 0) -
        (Number(trialStatus?.trial_revenue) || 0),
    ),
    trial_progress:
      trialStatus?.trial_threshold > 0
        ? ((Number(trialStatus?.trial_revenue) || 0) /
            (Number(trialStatus?.trial_threshold) || 1)) *
          100
        : 0,
  };

  const formatCurrency = (
    amount: number | string | null | undefined,
    currencyCode: string = "USD",
  ) => {
    if (amount === null || amount === undefined || amount === "") {
      return `$${0.0}`;
    }
    const numericAmount =
      typeof amount === "string" ? parseFloat(amount) : amount;
    if (isNaN(numericAmount)) {
      return `$${0.0}`;
    }
    return `$${numericAmount.toFixed(2)}`;
  };

  if (hasActiveSubscription) {
    return (
      <Card>
        <BlockStack gap="400">
          <InlineStack align="space-between">
            <Text as="h2" variant="headingMd" fontWeight="bold">
              🎉 Billing Active
            </Text>
            <Badge tone="success">Active</Badge>
          </InlineStack>

          <div
            style={{
              padding: "16px",
              backgroundColor: "#F0F9FF",
              borderRadius: "8px",
              border: "1px solid #0EA5E9",
            }}
          >
            <InlineStack gap="200" align="start">
              <Icon source={CheckCircleIcon} tone="success" />
              <BlockStack gap="200">
                <Text as="p" variant="bodyMd" fontWeight="medium">
                  Your usage-based billing is now active!
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  You'll be charged 3% of attributed revenue with a $1,000
                  monthly cap.
                </Text>
              </BlockStack>
            </InlineStack>
          </div>
        </BlockStack>
      </Card>
    );
  }

  if (isTrialCompleted && needsBillingSetup) {
    return (
      <Card>
        <BlockStack gap="400">
          <InlineStack align="space-between">
            <Text as="h2" variant="headingMd" fontWeight="bold">
              💳 Setup Billing Required
            </Text>
            <Badge tone="warning">Action Required</Badge>
          </InlineStack>

          <Banner tone="warning">
            <Text as="p">
              Your trial has completed! To continue using Better Bundle, please
              set up billing.
            </Text>
          </Banner>

          <div
            style={{
              padding: "20px",
              backgroundColor: "#FEF3C7",
              borderRadius: "8px",
              border: "1px solid #F59E0B",
            }}
          >
            <BlockStack gap="300">
              <InlineStack gap="200" align="start">
                <Icon source={AlertTriangleIcon} tone="warning" />
                <Text as="p" variant="bodyMd" fontWeight="medium">
                  Services are currently suspended
                </Text>
              </InlineStack>
              <Text as="p" variant="bodySm" tone="subdued">
                Your Better Bundle features are paused until billing is
                configured.
              </Text>
            </BlockStack>
          </div>

          <div
            style={{
              padding: "20px",
              backgroundColor: "#F8FAFC",
              borderRadius: "8px",
              border: "1px solid #E2E8F0",
            }}
          >
            <BlockStack gap="300">
              <Text as="h3" variant="headingSm" fontWeight="bold">
                Usage-Based Billing Plan
              </Text>

              <BlockStack gap="200">
                <InlineStack align="space-between">
                  <Text as="p" variant="bodyMd">
                    Base Price:
                  </Text>
                  <Text as="p" variant="bodyMd" fontWeight="medium">
                    $0.00/month
                  </Text>
                </InlineStack>
                <InlineStack align="space-between">
                  <Text as="p" variant="bodyMd">
                    Usage Fee:
                  </Text>
                  <Text as="p" variant="bodyMd" fontWeight="medium">
                    3% of attributed revenue
                  </Text>
                </InlineStack>
                <InlineStack align="space-between">
                  <Text as="p" variant="bodyMd">
                    Monthly Cap:
                  </Text>
                  <Text as="p" variant="bodyMd" fontWeight="medium">
                    $1,000.00
                  </Text>
                </InlineStack>
                <InlineStack align="space-between">
                  <Text as="p" variant="bodyMd">
                    Billing Cycle:
                  </Text>
                  <Text as="p" variant="bodyMd" fontWeight="medium">
                    Every 30 days
                  </Text>
                </InlineStack>
              </BlockStack>
            </BlockStack>
          </div>

          <Button
            primary
            size="large"
            onClick={onSetupBilling}
            loading={isLoading}
            icon={CreditCardIcon}
          >
            Setup Billing & Activate Services
          </Button>

          <Text as="p" variant="bodySm" tone="subdued" alignment="center">
            By setting up billing, you agree to our usage-based pricing model.
          </Text>
        </BlockStack>
      </Card>
    );
  }

  if (safeTrialStatus.is_trial_active) {
    return (
      <Card>
        <BlockStack gap="400">
          <InlineStack align="space-between">
            <Text as="h2" variant="headingMd" fontWeight="bold">
              🚀 Trial in Progress
            </Text>
            <Badge tone="info">Trial Active</Badge>
          </InlineStack>

          <div
            style={{
              padding: "20px",
              backgroundColor: "#F0F9FF",
              borderRadius: "8px",
              border: "1px solid #0EA5E9",
            }}
          >
            <BlockStack gap="300">
              <InlineStack gap="200" align="start">
                <Icon source={StarFilledIcon} tone="info" />
                <Text as="p" variant="bodyMd" fontWeight="medium">
                  You're currently in your free trial period
                </Text>
              </InlineStack>
              <Text as="p" variant="bodySm" tone="subdued">
                Once you reach ${safeTrialStatus.trial_threshold} in attributed
                revenue, you'll be prompted to set up billing.
              </Text>
            </BlockStack>
          </div>

          <BlockStack gap="300">
            <InlineStack align="space-between">
              <Text as="p" variant="bodyMd" fontWeight="medium">
                Trial Progress
              </Text>
              <Text as="p" variant="bodyMd">
                {formatCurrency(safeTrialStatus.trial_revenue, plan.currency)} /{" "}
                {formatCurrency(safeTrialStatus.trial_threshold, plan.currency)}
              </Text>
            </InlineStack>

            <ProgressBar
              progress={Math.min(safeTrialStatus.trial_progress, 100)}
              size="medium"
            />

            <Text as="p" variant="bodySm" tone="subdued" alignment="center">
              {safeTrialStatus.remaining_revenue > 0
                ? `${formatCurrency(safeTrialStatus.remaining_revenue, plan.currency)} remaining until trial completion`
                : "Trial threshold reached"}
            </Text>
          </BlockStack>

          <div
            style={{
              padding: "16px",
              backgroundColor: "#F8FAFC",
              borderRadius: "8px",
              border: "1px solid #E2E8F0",
            }}
          >
            <Text as="p" variant="bodySm" tone="subdued">
              <strong>What happens next?</strong> When your trial completes,
              you'll be automatically enrolled in our usage-based billing plan
              at 3% of attributed revenue (capped at $1,000/month).
            </Text>
          </div>
        </BlockStack>
      </Card>
    );
  }

  return (
    <Card>
      <BlockStack gap="400">
        <Text as="h2" variant="headingMd" fontWeight="bold">
          Billing Status
        </Text>
        <Text as="p" variant="bodyMd" tone="subdued">
          No billing information available.
        </Text>
      </BlockStack>
    </Card>
  );
}
