import {
  Banner,
  Button,
  BlockStack,
  InlineStack,
  Text,
  Icon,
  Card,
  Badge,
} from "@shopify/polaris";
import {
  AlertTriangleIcon,
  CreditCardIcon,
  CheckCircleIcon,
  StarFilledIcon,
} from "@shopify/polaris-icons";

interface TrialCompletionNotificationProps {
  trialStatus: {
    is_trial_active?: boolean;
    trial_threshold?: number;
    trial_revenue?: number;
    remaining_revenue: number;
    trial_progress: number;
  };
  billingConfig: any;
  onSetupBilling: () => void;
  onDismiss: () => void;
  isLoading?: boolean;
}

export function TrialCompletionNotification({
  trialStatus,
  billingConfig,
  onSetupBilling,
  onDismiss,
  isLoading = false,
}: TrialCompletionNotificationProps) {
  const isTrialCompleted = !trialStatus.is_trial_active && billingConfig?.trial_completed_at;
  const needsBillingSetup = billingConfig?.subscription_required && !billingConfig?.subscription_id;
  const hasActiveSubscription = billingConfig?.subscription_id && billingConfig?.subscription_status === "ACTIVE";
  const subscriptionPending = billingConfig?.subscription_id && billingConfig?.subscription_status === "PENDING";

  // Don't show notification if trial is still active
  if (trialStatus.is_trial_active) {
    return null;
  }

  // Show success notification if subscription is active
  if (hasActiveSubscription) {
    return (
      <Banner tone="success" onDismiss={onDismiss}>
        <BlockStack gap="200">
          <InlineStack gap="200" align="start">
            <Icon source={CheckCircleIcon} tone="success" />
            <BlockStack gap="100">
              <Text as="p" variant="bodyMd" fontWeight="medium">
                🎉 Trial completed! Your usage-based billing is now active.
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                You'll be charged 3% of attributed revenue with a $1,000 monthly cap.
              </Text>
            </BlockStack>
          </InlineStack>
        </BlockStack>
      </Banner>
    );
  }

  // Show pending notification if subscription is pending approval
  if (subscriptionPending) {
    return (
      <Banner tone="info" onDismiss={onDismiss}>
        <BlockStack gap="200">
          <InlineStack gap="200" align="start">
            <Icon source={StarFilledIcon} tone="info" />
            <BlockStack gap="100">
              <Text as="p" variant="bodyMd" fontWeight="medium">
                ⏳ Billing subscription pending approval
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                Your billing setup is being processed. Services will resume once approved.
              </Text>
            </BlockStack>
          </InlineStack>
        </BlockStack>
      </Banner>
    );
  }

  // Show critical notification if billing setup is required
  if (isTrialCompleted && needsBillingSetup) {
    return (
      <Card>
        <BlockStack gap="400">
          <Banner tone="critical">
            <BlockStack gap="300">
              <InlineStack gap="200" align="start">
                <Icon source={AlertTriangleIcon} tone="critical" />
                <BlockStack gap="100">
                  <Text as="p" variant="bodyMd" fontWeight="bold">
                    🚨 Trial Completed - Billing Setup Required
                  </Text>
                  <Text as="p" variant="bodySm">
                    Your trial has ended. Services are suspended until billing is configured.
                  </Text>
                </BlockStack>
              </InlineStack>
            </BlockStack>
          </Banner>

          <div style={{ 
            padding: "20px", 
            backgroundColor: "#FEF3C7", 
            borderRadius: "8px", 
            border: "1px solid #F59E0B" 
          }}>
            <BlockStack gap="300">
              <Text as="h3" variant="headingSm" fontWeight="bold">
                What happens next?
              </Text>
              <BlockStack gap="200">
                <Text as="p" variant="bodySm">
                  • Your Better Bundle features are currently paused
                </Text>
                <Text as="p" variant="bodySm">
                  • Set up usage-based billing to reactivate services
                </Text>
                <Text as="p" variant="bodySm">
                  • You'll be charged 3% of attributed revenue (capped at $1,000/month)
                </Text>
              </BlockStack>
            </BlockStack>
          </div>

          <div style={{ 
            padding: "16px", 
            backgroundColor: "#F8FAFC", 
            borderRadius: "8px", 
            border: "1px solid #E2E8F0" 
          }}>
            <BlockStack gap="200">
              <Text as="h4" variant="bodyMd" fontWeight="medium">
                Usage-Based Billing Plan
              </Text>
              <BlockStack gap="100">
                <InlineStack align="space-between">
                  <Text as="p" variant="bodySm">Base Price:</Text>
                  <Text as="p" variant="bodySm" fontWeight="medium">$0.00/month</Text>
                </InlineStack>
                <InlineStack align="space-between">
                  <Text as="p" variant="bodySm">Usage Fee:</Text>
                  <Text as="p" variant="bodySm" fontWeight="medium">3% of attributed revenue</Text>
                </InlineStack>
                <InlineStack align="space-between">
                  <Text as="p" variant="bodySm">Monthly Cap:</Text>
                  <Text as="p" variant="bodySm" fontWeight="medium">$1,000.00</Text>
                </InlineStack>
              </BlockStack>
            </BlockStack>
          </div>

          <InlineStack gap="300" align="space-between">
            <Button
              primary
              size="large"
              onClick={onSetupBilling}
              loading={isLoading}
              icon={CreditCardIcon}
            >
              Setup Billing & Reactivate Services
            </Button>
            <Button onClick={onDismiss} disabled={isLoading}>
              Dismiss
            </Button>
          </InlineStack>

          <Text as="p" variant="bodySm" tone="subdued" alignment="center">
            By setting up billing, you agree to our usage-based pricing model.
          </Text>
        </BlockStack>
      </Card>
    );
  }

  return null;
}

/**
 * Hook to get trial completion notification data
 */
export function useTrialCompletionNotification(billingData: any) {
  const plan = billingData?.billing_plan;
  const trialStatus = plan?.trial_status;
  const config = plan?.configuration || {};

  const isTrialCompleted = !trialStatus?.is_trial_active && config?.trial_completed_at;
  const needsBillingSetup = config?.subscription_required && !config?.subscription_id;
  const hasActiveSubscription = config?.subscription_id && config?.subscription_status === "ACTIVE";
  const subscriptionPending = config?.subscription_id && config?.subscription_status === "PENDING";

  return {
    showNotification: isTrialCompleted || hasActiveSubscription || subscriptionPending,
    isTrialCompleted,
    needsBillingSetup,
    hasActiveSubscription,
    subscriptionPending,
    trialStatus,
    billingConfig: config,
  };
}
