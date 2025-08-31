import React from "react";
import {
  Page,
  Layout,
  Card,
  BlockStack,
  Text,
  Button,
  ProgressBar,
  Box,
  Banner,
  EmptyState,
  List,
  SkeletonBodyText,
  SkeletonDisplayText,
  SkeletonThumbnail,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import type { AnalysisState, ErrorState } from "../../types";

interface DashboardStateProps {
  state: AnalysisState;
  error?: ErrorState;
  progress?: number;
  jobId?: string;
  isSubmitting?: boolean;
  onStartAnalysis: () => void;
  onRetry?: () => void;
}

export function DashboardState({
  state,
  error,
  progress = 0,
  jobId,
  isSubmitting = false,
  onStartAnalysis,
  onRetry,
}: DashboardStateProps) {
  if (state === "idle") {
    return (
      <Page>
        <TitleBar title="BetterBundle - Smart Bundle Analysis" />
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="500" align="center">
                <Box padding="500">
                  <Text variant="headingLg" as="h2">
                    🚀 Discover Bundle Opportunities
                  </Text>
                </Box>
                <BlockStack gap="300" align="center">
                  <Text
                    variant="bodyMd"
                    as="p"
                    tone="subdued"
                    alignment="center"
                  >
                    Let us analyze your store's order data to find products that
                    customers love buying together. This can help increase your
                    sales and customer satisfaction!
                  </Text>
                  <Button
                    variant="primary"
                    size="large"
                    onClick={onStartAnalysis}
                    loading={isSubmitting}
                    disabled={isSubmitting}
                  >
                    {isSubmitting
                      ? "🚀 Starting..."
                      : "🎯 Start Smart Analysis"}
                  </Button>
                </BlockStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  if (state === "loading" || state === "checking") {
    return (
      <Page>
        <TitleBar title="BetterBundle - Analyzing Your Store" />
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="500" align="center">
                <BlockStack gap="400" align="center">
                  {/* Header with clear analysis info */}
                  <BlockStack gap="300" align="center">
                    <Text variant="headingLg" as="h1" alignment="center">
                      {state === "checking" && "🚀 Starting Your Analysis"}
                      {state === "loading" && "🔍 Analyzing Your Store"}
                    </Text>
                    <Text
                      variant="bodyMd"
                      as="p"
                      tone="subdued"
                      alignment="center"
                    >
                      We're analyzing your store data to discover bundle
                      opportunities that can boost your sales and customer
                      satisfaction.
                    </Text>
                  </BlockStack>

                  {/* Status section */}
                  <BlockStack gap="400" align="center">
                    <Text
                      variant="bodyMd"
                      as="p"
                      tone="subdued"
                      alignment="center"
                    >
                      {state === "checking" && "⏳ Preparing analysis..."}
                      {state === "loading" &&
                        "🚀 Analysis is running in the background. You'll be notified when it's complete!"}
                    </Text>
                  </BlockStack>

                  {/* Skeleton content to show what's being analyzed */}
                  <BlockStack gap="400" align="center">
                    <Text variant="headingSm" as="h3" alignment="center">
                      🔍 What we're analyzing:
                    </Text>

                    <Layout>
                      <Layout.Section>
                        <Card padding="400">
                          <BlockStack gap="400" align="center">
                            <SkeletonThumbnail size="medium" />
                            <SkeletonBodyText lines={2} />
                            <Text
                              variant="bodySm"
                              as="p"
                              tone="subdued"
                              alignment="center"
                            >
                              📦 Order Data
                            </Text>
                            <Text
                              variant="bodySm"
                              as="p"
                              tone="subdued"
                              alignment="center"
                            >
                              Analyzing customer purchase patterns
                            </Text>
                          </BlockStack>
                        </Card>
                      </Layout.Section>

                      <Layout.Section>
                        <Card padding="400">
                          <BlockStack gap="400" align="center">
                            <SkeletonThumbnail size="medium" />
                            <SkeletonBodyText lines={2} />
                            <Text
                              variant="bodySm"
                              as="p"
                              tone="subdued"
                              alignment="center"
                            >
                              🛍️ Product Data
                            </Text>
                            <Text
                              variant="bodySm"
                              as="p"
                              tone="subdued"
                              alignment="center"
                            >
                              Processing product relationships
                            </Text>
                          </BlockStack>
                        </Card>
                      </Layout.Section>

                      <Layout.Section>
                        <Card padding="400">
                          <BlockStack gap="400" align="center">
                            <SkeletonThumbnail size="medium" />
                            <SkeletonBodyText lines={2} />
                            <Text
                              variant="bodySm"
                              as="p"
                              tone="subdued"
                              alignment="center"
                            >
                              🧠 ML Analysis
                            </Text>
                            <Text
                              variant="bodySm"
                              as="p"
                              tone="subdued"
                              alignment="center"
                            >
                              Finding optimal bundle combinations
                            </Text>
                          </BlockStack>
                        </Card>
                      </Layout.Section>
                    </Layout>
                  </BlockStack>

                  {/* Estimated time and job info */}
                  <BlockStack gap="200" align="center">
                    <Text
                      variant="bodySm"
                      as="p"
                      tone="subdued"
                      alignment="center"
                    >
                      ⏱️ Estimated time: 2-5 minutes
                    </Text>
                    <Text
                      variant="bodySm"
                      as="p"
                      tone="subdued"
                      alignment="center"
                    >
                      🔔 You'll receive a notification when the analysis is
                      complete
                    </Text>
                    <Text
                      variant="bodySm"
                      as="p"
                      tone="subdued"
                      alignment="center"
                    >
                      💡 This is a one-time analysis. Future updates will be
                      faster!
                    </Text>
                    {jobId && (
                      <Text
                        variant="bodySm"
                        as="p"
                        tone="subdued"
                        alignment="center"
                      >
                        🔍 Job ID: {jobId.substring(0, 8)}...
                      </Text>
                    )}
                  </BlockStack>
                </BlockStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  if (state === "error" && error) {
    return (
      <Page>
        <TitleBar title="BetterBundle - Analysis Error" />
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="500" align="center">
                <Banner title={`❌ ${error.title}`} tone="critical">
                  <p>{error.description}</p>
                </Banner>

                {error.recommendations && (
                  <BlockStack gap="300">
                    <Text as="h3" variant="headingMd">
                      💡 What you can try:
                    </Text>
                    <List>
                      {error.recommendations.map((rec, index) => (
                        <List.Item key={index}>{rec}</List.Item>
                      ))}
                    </List>
                  </BlockStack>
                )}

                <BlockStack gap="300">
                  <Button variant="primary" onClick={onStartAnalysis}>
                    🔄 Try Again
                  </Button>
                </BlockStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  if (state === "no-data") {
    return (
      <Page>
        <TitleBar title="BetterBundle - No Bundles Found" />
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="500" align="center">
                <EmptyState
                  heading="📊 No bundle opportunities found yet"
                  image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                >
                  <p>
                    We analyzed your store but couldn't find significant bundle
                    opportunities at this time. This might be because you need
                    more order data or different product combinations.
                  </p>
                </EmptyState>

                <BlockStack gap="300">
                  <Button variant="primary" onClick={onStartAnalysis}>
                    🔄 Try Analysis Again
                  </Button>
                </BlockStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  if (state === "success") {
    return (
      <Page>
        <TitleBar title="BetterBundle - Analysis Complete" />
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="500" align="center">
                <Banner title="🎉 Analysis Complete!" tone="success">
                  <p>
                    Great news! We've found bundle opportunities in your store
                    that can help increase your sales.
                  </p>
                </Banner>

                <BlockStack gap="300" align="center">
                  <Text as="h2" variant="headingMd">
                    🎯 Bundle Opportunities Discovered
                  </Text>
                  <Text
                    variant="bodyMd"
                    as="p"
                    tone="subdued"
                    alignment="center"
                  >
                    We've analyzed your store data and identified products that
                    customers love buying together. These bundles can help boost
                    your average order value and customer satisfaction.
                  </Text>
                </BlockStack>

                <BlockStack gap="300">
                  <Button variant="primary" onClick={onStartAnalysis}>
                    🔄 Run New Analysis
                  </Button>
                  {onRetry && (
                    <Button variant="secondary" onClick={onRetry}>
                      📊 View Dashboard
                    </Button>
                  )}
                </BlockStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  return null;
}
