import React from "react";
import {
  Page,
  Layout,
  Card,
  BlockStack,
  Text,
  Button,
  Spinner,
  ProgressBar,
  Box,
  Banner,
  EmptyState,
  List,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import type { AnalysisState, ErrorState } from "../../types";

interface DashboardStateProps {
  state: AnalysisState;
  error?: ErrorState;
  progress?: number;
  onStartAnalysis: () => void;
  onRetry?: () => void;
}

export function DashboardState({
  state,
  error,
  progress = 0,
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
                    Analyze your store's order data to find products that
                    customers love buying together.
                  </Text>
                  <Button
                    variant="primary"
                    size="large"
                    onClick={onStartAnalysis}
                  >
                    Start Smart Analysis
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
                <Spinner size="large" />
                <BlockStack gap="300" align="center">
                  <Text as="h2" variant="headingMd">
                    Analyzing Your Store's Orders
                  </Text>
                  <Text
                    variant="bodyMd"
                    as="p"
                    tone="subdued"
                    alignment="center"
                  >
                    We're analyzing your order data to discover bundle
                    opportunities.
                  </Text>

                  <BlockStack gap="300" align="center">
                    <Box
                      paddingInlineStart="400"
                      paddingInlineEnd="400"
                      minWidth="300px"
                    >
                      <ProgressBar progress={progress} size="small" />
                    </Box>
                    <Text variant="bodySm" as="p" tone="subdued">
                      {progress < 20 &&
                        "🔍 Analyzing your store's unique patterns..."}
                      {progress >= 20 &&
                        progress < 40 &&
                        "⚡ Optimizing thresholds..."}
                      {progress >= 40 &&
                        progress < 60 &&
                        "🧠 Finding product combinations..."}
                      {progress >= 60 &&
                        progress < 80 &&
                        "🎯 Creating bundle opportunities..."}
                      {progress >= 80 &&
                        progress < 95 &&
                        "✨ Finalizing results..."}
                      {progress >= 95 && "🚀 Your bundles are ready!"}
                    </Text>
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
                <Banner title={error.title} tone="critical">
                  <p>{error.description}</p>
                </Banner>

                {error.recommendations && (
                  <BlockStack gap="300">
                    <Text as="h3" variant="headingMd">
                      💡 Recommendations
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
                    Start Analysis
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
                  heading="No bundle opportunities found"
                  image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                >
                  <p>
                    We analyzed your store but couldn't find significant bundle
                    opportunities.
                  </p>
                </EmptyState>

                <BlockStack gap="300">
                  <Button variant="primary" onClick={onStartAnalysis}>
                    Run Analysis Again
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
                <Banner title="Analysis Complete! 🎉" tone="success">
                  <p>
                    Your bundle analysis has completed successfully! We found
                    bundle opportunities in your store.
                  </p>
                </Banner>

                <BlockStack gap="300" align="center">
                  <Text as="h2" variant="headingMd">
                    🎯 Bundle Opportunities Found
                  </Text>
                  <Text
                    variant="bodyMd"
                    as="p"
                    tone="subdued"
                    alignment="center"
                  >
                    Your store has been analyzed and bundle opportunities have
                    been identified. You can now view and manage your bundle
                    recommendations.
                  </Text>
                </BlockStack>

                <BlockStack gap="300">
                  <Button variant="primary" onClick={onStartAnalysis}>
                    Run New Analysis
                  </Button>
                  {onRetry && (
                    <Button variant="secondary" onClick={onRetry}>
                      Back to Dashboard
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
