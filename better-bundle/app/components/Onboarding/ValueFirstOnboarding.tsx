/**
 * Value-First Onboarding Flow
 *
 * Industry Pattern 1: Install → Setup → Free Trial → Value Demo → Consent → Billing
 *
 * This follows the most successful SaaS onboarding patterns used by:
 * - Klaviyo, ReCharge, Bold Apps (Shopify)
 * - Stripe, HubSpot, Slack (SaaS)
 */

import React, { useState, useEffect } from "react";
import {
  Card,
  Text,
  BlockStack,
  InlineStack,
  Button,
  Banner,
  ProgressBar,
  Layout,
  Page,
  Box,
  Icon,
  Badge,
  Divider,
  List,
} from "@shopify/polaris";
import {
  CheckCircleIcon,
  ArrowRightIcon,
  StarIcon,
  TrendingUpIcon,
  DollarSignIcon,
} from "@shopify/polaris-icons";

interface OnboardingStep {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  action: string;
  completed: boolean;
  value?: string;
}

interface ValueFirstOnboardingProps {
  isNewInstallation: boolean;
  trialStatus: {
    isTrialActive: boolean;
    currentRevenue: number;
    threshold: number;
    remainingRevenue: number;
    progress: number;
  };
  onComplete: () => void;
}

export function ValueFirstOnboarding({
  isNewInstallation,
  trialStatus,
  onComplete,
}: ValueFirstOnboardingProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<Set<string>>(new Set());

  const onboardingSteps: OnboardingStep[] = [
    {
      id: "welcome",
      title: "Welcome to Better Bundle! 🎉",
      description:
        "Let's get your recommendation engine set up and start boosting your sales.",
      icon: <StarIcon />,
      action: "Get Started",
      completed: false,
      value: "Immediate setup in under 2 minutes",
    },
    {
      id: "setup",
      title: "Configure Your Recommendations",
      description:
        "Customize how recommendations appear to match your store's style and brand.",
      icon: <CheckCircleIcon />,
      action: "Configure Now",
      completed: false,
      value: "Personalized to your store",
    },
    {
      id: "preview",
      title: "Preview Your Recommendations",
      description:
        "See exactly how recommendations will look to your customers.",
      icon: <ArrowRightIcon />,
      action: "Preview",
      completed: false,
      value: "See results before going live",
    },
    {
      id: "activate",
      title: "Activate & Start Earning",
      description:
        "Turn on recommendations and start generating more sales immediately.",
      icon: <TrendingUpIcon />,
      action: "Activate Now",
      completed: false,
      value: "Start earning from day 1",
    },
  ];

  const handleStepAction = async (step: OnboardingStep) => {
    try {
      // Mark step as completed
      setCompletedSteps((prev) => new Set([...prev, step.id]));

      // Handle specific step actions
      switch (step.id) {
        case "welcome":
          // Just move to next step
          setCurrentStep(1);
          break;

        case "setup":
          // Open configuration modal/page
          await handleConfiguration();
          setCurrentStep(2);
          break;

        case "preview":
          // Show preview
          await handlePreview();
          setCurrentStep(3);
          break;

        case "activate":
          // Activate recommendations
          await handleActivation();
          onComplete();
          break;
      }
    } catch (error) {
      console.error("Error handling step action:", error);
    }
  };

  const handleConfiguration = async () => {
    // Open configuration modal or redirect to settings
    console.log("Opening configuration...");
    // Implementation would open configuration modal
  };

  const handlePreview = async () => {
    // Show preview of recommendations
    console.log("Showing preview...");
    // Implementation would show preview
  };

  const handleActivation = async () => {
    // Activate recommendations
    console.log("Activating recommendations...");
    // Implementation would activate recommendations
  };

  // Don't show onboarding for existing users
  if (!isNewInstallation) {
    return null;
  }

  const currentStepData = onboardingSteps[currentStep];
  const progress = ((currentStep + 1) / onboardingSteps.length) * 100;

  return (
    <Page>
      <Layout>
        <Layout.Section>
          <Card>
            <BlockStack gap="500">
              {/* Progress indicator */}
              <Box>
                <InlineStack align="space-between">
                  <Text as="h2" variant="headingLg">
                    Getting Started
                  </Text>
                  <Badge tone="info">
                    Step {currentStep + 1} of {onboardingSteps.length}
                  </Badge>
                </InlineStack>
                <Box paddingBlockStart="300">
                  <ProgressBar progress={progress} size="small" />
                </Box>
              </Box>

              {/* Current step content */}
              <Card sectioned>
                <BlockStack gap="400">
                  <InlineStack align="start" gap="300">
                    <Box>
                      <Icon source={currentStepData.icon} />
                    </Box>
                    <BlockStack gap="200">
                      <Text as="h3" variant="headingMd">
                        {currentStepData.title}
                      </Text>
                      <Text as="p" variant="bodyMd">
                        {currentStepData.description}
                      </Text>
                      {currentStepData.value && (
                        <Badge tone="success">{currentStepData.value}</Badge>
                      )}
                    </BlockStack>
                  </InlineStack>

                  {/* Trial status banner */}
                  {trialStatus.isTrialActive && (
                    <Banner tone="info">
                      <BlockStack gap="200">
                        <Text as="p">
                          <strong>Free Trial Active:</strong> You're currently
                          in your free trial period.
                        </Text>
                        <Text as="p">
                          Generate ${trialStatus.remainingRevenue.toFixed(2)}{" "}
                          more in attributed revenue to complete your trial and
                          start billing.
                        </Text>
                        <Box>
                          <ProgressBar
                            progress={trialStatus.progress}
                            size="small"
                          />
                        </Box>
                      </BlockStack>
                    </Banner>
                  )}

                  <Divider />

                  <InlineStack align="end">
                    <Button
                      variant="primary"
                      size="large"
                      onClick={() => handleStepAction(currentStepData)}
                    >
                      {currentStepData.action}
                    </Button>
                  </InlineStack>
                </BlockStack>
              </Card>

              {/* Benefits section */}
              <Card sectioned>
                <BlockStack gap="300">
                  <Text as="h4" variant="headingSm">
                    What you'll get:
                  </Text>
                  <List>
                    <List.Item>
                      <strong>Increased Sales:</strong> Average 15-25% boost in
                      revenue
                    </List.Item>
                    <List.Item>
                      <strong>Better Customer Experience:</strong> Personalized
                      product suggestions
                    </List.Item>
                    <List.Item>
                      <strong>Easy Setup:</strong> Works automatically with your
                      existing products
                    </List.Item>
                    <List.Item>
                      <strong>No Risk:</strong> Free trial until you generate
                      $200 in attributed revenue
                    </List.Item>
                  </List>
                </BlockStack>
              </Card>

              {/* Industry social proof */}
              <Card sectioned>
                <BlockStack gap="300">
                  <Text as="h4" variant="headingSm">
                    Trusted by thousands of Shopify stores
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
                        2 min
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Setup Time
                      </Text>
                    </Box>
                  </InlineStack>
                </BlockStack>
              </Card>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
