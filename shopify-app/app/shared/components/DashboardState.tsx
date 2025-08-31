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
  Spinner,
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
  console.log("🎨 DashboardState render:", {
    state,
    hasError: !!error,
    errorTitle: error?.title,
    errorDescription: error?.description,
    progress,
    jobId,
    isSubmitting,
  });

  if (state === "idle") {
    return (
      <Page>
        <TitleBar title="BetterBundle - Bundle Analysis" />
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="500" align="center">
                <Text as="h1" variant="headingLg">
                  🎯 Bundle Analysis
                </Text>
                <Text as="p" variant="bodyMd">
                  Analyze your store's data to discover optimal product bundles
                  and increase your average order value.
                </Text>
                <Button
                  variant="primary"
                  size="large"
                  onClick={() => {
                    console.log("🔘 Button clicked!", { isSubmitting, state });
                    onStartAnalysis();
                  }}
                  disabled={isSubmitting}
                  loading={isSubmitting}
                >
                  {isSubmitting ? "Starting..." : "🚀 Start Analysis"}
                </Button>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  if (state === "queued") {
    return (
      <Page>
        <TitleBar title="BetterBundle - Analysis in Progress" />
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="500" align="center">
                <Text as="h2" variant="headingMd">
                  🚀 Analysis in Progress
                </Text>
                <Text as="p" variant="bodyMd">
                  We're analyzing your store data to discover optimal product
                  bundles.
                </Text>

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
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  if (state === "error" && error) {
    console.log("🎨 Rendering error state:", error);
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
