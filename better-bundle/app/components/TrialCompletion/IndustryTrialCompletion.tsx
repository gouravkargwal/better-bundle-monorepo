/**
 * Industry-Standard Trial Completion Flow
 *
 * Based on successful patterns from:
 * - Klaviyo: Value demonstration → Clear benefits → Easy upgrade
 * - ReCharge: Results showcase → Pricing transparency → One-click upgrade
 * - Bold Apps: ROI proof → Feature benefits → Seamless billing
 */

import React, { useState } from "react";
import {
  Modal,
  Text,
  BlockStack,
  InlineStack,
  Button,
  Card,
  Banner,
  List,
  Box,
  Icon,
  Badge,
  Divider,
  ProgressBar,
} from "@shopify/polaris";
import {
  CheckCircleIcon,
  TrendingUpIcon,
  DollarSignIcon,
  StarIcon,
  ArrowRightIcon,
} from "@shopify/polaris-icons";

interface IndustryTrialCompletionProps {
  isOpen: boolean;
  onClose: () => void;
  trialData: {
    revenue: number;
    threshold: number;
    currency: string;
    period: string;
    attributedOrders: number;
    conversionRate: number;
  };
  onConsent: () => void;
  onContinueFree: () => void;
}

export function IndustryTrialCompletion({
  isOpen,
  onClose,
  trialData,
  onConsent,
  onContinueFree,
}: IndustryTrialCompletionProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState("growth");

  const plans = {
    starter: {
      name: "Starter",
      price: "3% of attributed revenue",
      max: "$50/month",
      features: [
        "Basic recommendations",
        "Standard analytics",
        "Email support",
      ],
      recommended: false,
    },
    growth: {
      name: "Growth",
      price: "3% of attributed revenue",
      max: "$200/month",
      features: [
        "Advanced recommendations",
        "Full analytics",
        "Priority support",
        "A/B testing",
      ],
      recommended: true,
    },
    enterprise: {
      name: "Enterprise",
      price: "2.5% of attributed revenue",
      max: "$1000/month",
      features: [
        "Custom algorithms",
        "Advanced analytics",
        "Dedicated support",
        "Custom integrations",
      ],
      recommended: false,
    },
  };

  const handleConsent = async () => {
    setIsLoading(true);
    try {
      // Create subscription with consent
      await createSubscriptionWithConsent(selectedPlan);
      onConsent();
    } catch (error) {
      console.error("Error creating subscription:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const createSubscriptionWithConsent = async (plan: string) => {
    // Implementation would create the subscription
    console.log("Creating subscription for plan:", plan);
  };

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title="🎉 Congratulations! Your Trial is Complete"
      size="large"
      primaryAction={{
        content: "Start Billing",
        onAction: handleConsent,
        loading: isLoading,
      }}
      secondaryActions={[
        {
          content: "Continue Free (Limited)",
          onAction: onContinueFree,
        },
      ]}
    >
      <Modal.Section>
        <BlockStack gap="500">
          {/* Success banner with results */}
          <Banner tone="success">
            <BlockStack gap="300">
              <Text as="p">
                <strong>Amazing results!</strong> You've generated{" "}
                {trialData.currency}${trialData.revenue.toFixed(2)} in
                attributed revenue.
              </Text>
              <InlineStack gap="400" wrap={false}>
                <Box>
                  <Text as="p" variant="bodyMd" fontWeight="bold">
                    {trialData.attributedOrders} orders
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Attributed to Better Bundle
                  </Text>
                </Box>
                <Box>
                  <Text as="p" variant="bodyMd" fontWeight="bold">
                    {trialData.conversionRate}%
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Conversion Rate
                  </Text>
                </Box>
                <Box>
                  <Text as="p" variant="bodyMd" fontWeight="bold">
                    {trialData.currency}${trialData.revenue.toFixed(2)}
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Attributed Revenue
                  </Text>
                </Box>
              </InlineStack>
            </BlockStack>
          </Banner>

          {/* Value demonstration */}
          <Card sectioned>
            <BlockStack gap="400">
              <Text as="h3" variant="headingMd">
                Your Results Speak for Themselves
              </Text>

              <BlockStack gap="300">
                <InlineStack align="start" gap="300">
                  <Icon source={TrendingUpIcon} />
                  <BlockStack gap="100">
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      Revenue Growth
                    </Text>
                    <Text as="p" variant="bodySm">
                      Better Bundle generated {trialData.currency}$
                      {trialData.revenue.toFixed(2)} in additional revenue for
                      your store
                    </Text>
                  </BlockStack>
                </InlineStack>

                <InlineStack align="start" gap="300">
                  <Icon source={CheckCircleIcon} />
                  <BlockStack gap="100">
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      Proven Performance
                    </Text>
                    <Text as="p" variant="bodySm">
                      {trialData.attributedOrders} orders directly attributed to
                      our recommendations
                    </Text>
                  </BlockStack>
                </InlineStack>

                <InlineStack align="start" gap="300">
                  <Icon source={StarIcon} />
                  <BlockStack gap="100">
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      Customer Satisfaction
                    </Text>
                    <Text as="p" variant="bodySm">
                      Better product discovery leads to happier customers and
                      higher lifetime value
                    </Text>
                  </BlockStack>
                </InlineStack>
              </BlockStack>
            </BlockStack>
          </Card>

          {/* Pricing plans */}
          <Card sectioned>
            <BlockStack gap="400">
              <Text as="h3" variant="headingMd">
                Choose Your Plan
              </Text>
              <Text as="p" variant="bodyMd">
                Pay only for the revenue you generate. No minimums, no hidden
                fees.
              </Text>

              <InlineStack gap="300" wrap={false}>
                {Object.entries(plans).map(([key, plan]) => (
                  <Card
                    key={key}
                    sectioned
                    background={
                      plan.recommended ? "bg-surface-info" : undefined
                    }
                  >
                    <BlockStack gap="300">
                      {plan.recommended && (
                        <Badge tone="info">Recommended</Badge>
                      )}

                      <Text as="h4" variant="headingSm">
                        {plan.name}
                      </Text>

                      <Text as="p" variant="bodyMd" fontWeight="bold">
                        {plan.price}
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Max: {plan.max}
                      </Text>

                      <List>
                        {plan.features.map((feature, index) => (
                          <List.Item key={index}>{feature}</List.Item>
                        ))}
                      </List>

                      <Button
                        variant={plan.recommended ? "primary" : "secondary"}
                        size="slim"
                        onClick={() => setSelectedPlan(key)}
                      >
                        {selectedPlan === key ? "Selected" : "Select"}
                      </Button>
                    </BlockStack>
                  </Card>
                ))}
              </InlineStack>
            </BlockStack>
          </Card>

          {/* Billing transparency */}
          <Card sectioned>
            <BlockStack gap="300">
              <Text as="h4" variant="headingSm">
                Billing Details
              </Text>

              <List>
                <List.Item>
                  <strong>Pay-as-you-earn:</strong> Only pay when you generate
                  revenue
                </List.Item>
                <List.Item>
                  <strong>No minimums:</strong> No monthly fees or minimum
                  charges
                </List.Item>
                <List.Item>
                  <strong>Transparent pricing:</strong> Clear commission on
                  attributed revenue only
                </List.Item>
                <List.Item>
                  <strong>Cancel anytime:</strong> No long-term contracts or
                  commitments
                </List.Item>
              </List>
            </BlockStack>
          </Card>

          {/* Social proof */}
          <Card sectioned>
            <BlockStack gap="300">
              <Text as="h4" variant="headingSm">
                Join thousands of successful stores
              </Text>

              <InlineStack gap="400" wrap={false}>
                <Box>
                  <Text as="p" variant="bodyMd" fontWeight="bold">
                    4.9/5 ⭐
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    App Store Rating
                  </Text>
                </Box>
                <Box>
                  <Text as="p" variant="bodyMd" fontWeight="bold">
                    15-25%
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Average Revenue Increase
                  </Text>
                </Box>
                <Box>
                  <Text as="p" variant="bodyMd" fontWeight="bold">
                    10,000+
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Active Stores
                  </Text>
                </Box>
              </InlineStack>
            </BlockStack>
          </Card>
        </BlockStack>
      </Modal.Section>
    </Modal>
  );
}
