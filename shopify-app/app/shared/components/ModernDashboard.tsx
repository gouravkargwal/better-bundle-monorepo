import React, { useState, useEffect } from "react";
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
  Badge,
  DataTable,
  Tabs,
  Icon,
  InlineStack,
  Thumbnail,
  Link,
  Modal,
  TextField,
  Select,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import {
  AnalyticsMajor,
  AnalyticsMinor,
  BundleIconMajor,
  BundleIconMinor,
  CancelMajor,
  CancelMinor,
  CheckmarkMajor,
  CheckmarkMinor,
  ClockMajor,
  ClockMinor,
  DataVisualizationMajor,
  DataVisualizationMinor,
  DiamondAlertMajor,
  DiamondAlertMinor,
  DiscountsMajor,
  DiscountsMinor,
  DynamicSourceMajor,
  DynamicSourceMinor,
  EmailMajor,
  EmailMinor,
  ExportMajor,
  ExportMinor,
  FilterMajor,
  FilterMinor,
  GlobeMajor,
  GlobeMinor,
  HomeMajor,
  HomeMinor,
  ImageMajor,
  ImageMinor,
  InventoryMajor,
  InventoryMinor,
  KeyMajor,
  KeyMinor,
  ListMajor,
  ListMinor,
  LocationMajor,
  LocationMinor,
  MarketingMajor,
  MarketingMinor,
  MoneyMajor,
  MoneyMinor,
  NotesMajor,
  NotesMinor,
  OrdersMajor,
  OrdersMinor,
  PackageMajor,
  PackageMinor,
  ProductsMajor,
  ProductsMinor,
  ProfileMajor,
  ProfileMinor,
  SettingsMajor,
  SettingsMinor,
  ThemeEditMajor,
  ThemeEditMajorMinor,
  TimelineAttachmentMajor,
  TimelineAttachmentMinor,
  TransactionMajor,
  TransactionMinor,
  ViewMajor,
  ViewMinor,
} from "@shopify/polaris-icons";
import type { AnalysisState, ErrorState } from "../../types";

interface ModernDashboardProps {
  state: AnalysisState;
  error?: ErrorState;
  progress?: number;
  jobId?: string;
  isSubmitting?: boolean;
  onStartAnalysis: () => void;
  onRetry?: () => void;
}

interface StreamStatus {
  name: string;
  count: number;
  status: "active" | "idle" | "error";
  lastActivity: string;
}

interface AnalysisJob {
  id: string;
  jobId: string;
  status: string;
  progress: number;
  createdAt: string;
  completedAt?: string;
  error?: string;
}

export function ModernDashboard({
  state,
  error,
  progress = 0,
  jobId,
  isSubmitting = false,
  onStartAnalysis,
  onRetry,
}: ModernDashboardProps) {
  const [selectedTab, setSelectedTab] = useState(0);
  const [streamStatus, setStreamStatus] = useState<StreamStatus[]>([]);
  const [analysisJobs, setAnalysisJobs] = useState<AnalysisJob[]>([]);
  const [showStreamModal, setShowStreamModal] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);

  // Mock stream status data (replace with real API calls)
  useEffect(() => {
    const mockStreams: StreamStatus[] = [
      {
        name: "betterbundle:data-jobs",
        count: 12,
        status: "active",
        lastActivity: "2 minutes ago",
      },
      {
        name: "betterbundle:ml-training",
        count: 3,
        status: "active",
        lastActivity: "5 minutes ago",
      },
      {
        name: "betterbundle:analysis-results",
        count: 8,
        status: "active",
        lastActivity: "1 minute ago",
      },
      {
        name: "betterbundle:user-notifications",
        count: 0,
        status: "idle",
        lastActivity: "Never",
      },
      {
        name: "betterbundle:features-computed",
        count: 15,
        status: "active",
        lastActivity: "30 seconds ago",
      },
    ];
    setStreamStatus(mockStreams);
  }, []);

  // Mock analysis jobs data (replace with real API calls)
  useEffect(() => {
    const mockJobs: AnalysisJob[] = [
      {
        id: "1",
        jobId: "analysis_1234567890_abc123",
        status: "completed",
        progress: 100,
        createdAt: "2024-01-15T10:30:00Z",
        completedAt: "2024-01-15T10:35:00Z",
      },
      {
        id: "2",
        jobId: "analysis_1234567891_def456",
        status: "processing",
        progress: 75,
        createdAt: "2024-01-15T11:00:00Z",
      },
    ];
    setAnalysisJobs(mockJobs);
  }, []);

  // Set up refresh interval
  useEffect(() => {
    if (state === "queued" || state === "processing") {
      const interval = setInterval(() => {
        // Refresh stream status and job progress
        console.log("🔄 Refreshing dashboard data...");
      }, 5000);
      setRefreshInterval(interval);

      return () => {
        if (interval) clearInterval(interval);
      };
    }
  }, [state]);

  const tabs = [
    {
      id: "overview",
      content: "Overview",
      accessibilityLabel: "Dashboard overview",
      panelID: "overview-panel",
    },
    {
      id: "streams",
      content: "Event Streams",
      accessibilityLabel: "Redis streams monitoring",
      panelID: "streams-panel",
    },
    {
      id: "jobs",
      content: "Analysis Jobs",
      accessibilityLabel: "Analysis job history",
      panelID: "jobs-panel",
    },
    {
      id: "insights",
      content: "Live Insights",
      accessibilityLabel: "Real-time insights",
      panelID: "insights-panel",
    },
  ];

  const renderOverview = () => (
    <Layout>
      <Layout.Section>
        <Card>
          <BlockStack gap="500">
            <Text as="h2" variant="headingMd">
              🚀 Real-Time Bundle Analysis
            </Text>
            <Text as="p" variant="bodyMd">
              Our modern event-driven system analyzes your store data in real-time using Redis Streams and AI-powered insights.
            </Text>
            
            {state === "idle" && (
              <Button
                variant="primary"
                size="large"
                onClick={onStartAnalysis}
                disabled={isSubmitting}
                loading={isSubmitting}
                icon={AnalyticsMajor}
              >
                {isSubmitting ? "Starting..." : "🚀 Start Real-Time Analysis"}
              </Button>
            )}

            {state === "queued" && (
              <BlockStack gap="400">
                <Banner title="🔄 Analysis in Progress" tone="info">
                  <p>Your analysis is being processed in real-time. Check the Event Streams tab to monitor progress.</p>
                </Banner>
                <ProgressBar progress={progress} size="large" />
                <Text variant="bodySm" tone="subdued">
                  Job ID: {jobId?.substring(0, 12)}...
                </Text>
              </BlockStack>
            )}
          </BlockStack>
        </Card>
      </Layout.Section>

      <Layout.Section>
        <Card>
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd">
              📊 System Status
            </Text>
            <Layout>
              <Layout.Section oneThird>
                <Card padding="400">
                  <BlockStack gap="200" align="center">
                    <Icon source={BundleIconMajor} color="success" />
                    <Text variant="headingMd" as="h4">
                      {streamStatus.filter(s => s.status === "active").length}
                    </Text>
                    <Text variant="bodySm" tone="subdued">
                      Active Streams
                    </Text>
                  </BlockStack>
                </Card>
              </Layout.Section>
              <Layout.Section oneThird>
                <Card padding="400">
                  <BlockStack gap="200" align="center">
                    <Icon source={DataVisualizationMajor} color="info" />
                    <Text variant="headingMd" as="h4">
                      {analysisJobs.filter(j => j.status === "completed").length}
                    </Text>
                    <Text variant="bodySm" tone="subdued">
                      Completed Jobs
                    </Text>
                  </BlockStack>
                </Card>
              </Layout.Section>
              <Layout.Section oneThird>
                <Card padding="400">
                  <BlockStack gap="200" align="center">
                    <Icon source={ClockMajor} color="warning" />
                    <Text variant="headingMd" as="h4">
                      {analysisJobs.filter(j => j.status === "processing").length}
                    </Text>
                    <Text variant="bodySm" tone="subdued">
                      Active Jobs
                    </Text>
                  </BlockStack>
                </Card>
              </Layout.Section>
            </Layout>
          </BlockStack>
        </Card>
      </Layout.Section>
    </Layout>
  );

  const renderStreams = () => (
    <Layout>
      <Layout.Section>
        <Card>
          <BlockStack gap="400">
            <InlineStack align="space-between">
              <Text as="h3" variant="headingMd">
                📡 Redis Streams Monitor
              </Text>
              <Button
                variant="secondary"
                size="small"
                onClick={() => setShowStreamModal(true)}
                icon={ViewMajor}
              >
                View Details
              </Button>
            </InlineStack>
            
            <DataTable
              columnContentTypes={["text", "numeric", "text", "text"]}
              headings={["Stream Name", "Message Count", "Status", "Last Activity"]}
              rows={streamStatus.map(stream => [
                stream.name,
                stream.count.toString(),
                <Badge tone={stream.status === "active" ? "success" : stream.status === "idle" ? "info" : "critical"}>
                  {stream.status}
                </Badge>,
                stream.lastActivity,
              ])}
            />
          </BlockStack>
        </Card>
      </Layout.Section>
    </Layout>
  );

  const renderJobs = () => (
    <Layout>
      <Layout.Section>
        <Card>
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd">
              🔍 Analysis Job History
            </Text>
            
            {analysisJobs.length === 0 ? (
              <EmptyState
                heading="No analysis jobs yet"
                image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
              >
                <p>Start your first analysis to see job history here.</p>
              </EmptyState>
            ) : (
              <DataTable
                columnContentTypes={["text", "text", "numeric", "text", "text"]}
                headings={["Job ID", "Status", "Progress", "Created", "Completed"]}
                rows={analysisJobs.map(job => [
                  job.jobId.substring(0, 12) + "...",
                  <Badge tone={job.status === "completed" ? "success" : job.status === "processing" ? "info" : "warning"}>
                    {job.status}
                  </Badge>,
                  `${job.progress}%`,
                  new Date(job.createdAt).toLocaleDateString(),
                  job.completedAt ? new Date(job.completedAt).toLocaleDateString() : "-",
                ])}
              />
            )}
          </BlockStack>
        </Card>
      </Layout.Section>
    </Layout>
  );

  const renderInsights = () => (
    <Layout>
      <Layout.Section>
        <Card>
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd">
              💡 Live Insights
            </Text>
            
            <Banner title="🔄 Real-Time Processing" tone="info">
              <p>Your analysis results are being computed in real-time. Check back here for live insights as they become available.</p>
            </Banner>

            <Layout>
              <Layout.Section oneHalf>
                <Card padding="400">
                  <BlockStack gap="300">
                    <Text variant="headingSm" as="h4">
                      🧠 AI Processing
                    </Text>
                    <Text variant="bodySm" tone="subdued">
                      Our AI models are analyzing your data patterns in real-time to discover optimal product bundles.
                    </Text>
                    <InlineStack gap="200">
                      <Icon source={AnalyticsMinor} />
                      <Text variant="bodySm">Pattern Recognition</Text>
                    </InlineStack>
                    <InlineStack gap="200">
                      <Icon source={BundleIconMinor} />
                      <Text variant="bodySm">Bundle Optimization</Text>
                    </InlineStack>
                    <InlineStack gap="200">
                      <Icon source={MoneyMinor} />
                      <Text variant="bodySm">Revenue Prediction</Text>
                    </InlineStack>
                  </BlockStack>
                </Card>
              </Layout.Section>
              
              <Layout.Section oneHalf>
                <Card padding="400">
                  <BlockStack gap="300">
                    <Text variant="headingSm" as="h4">
                      📊 Data Pipeline
                    </Text>
                    <Text variant="bodySm" tone="subdued">
                      Your data flows through our event-driven pipeline for real-time processing and insights.
                    </Text>
                    <InlineStack gap="200">
                      <Icon source={DynamicSourceMinor} />
                      <Text variant="bodySm">Data Collection</Text>
                    </InlineStack>
                    <InlineStack gap="200">
                      <Icon source={FilterMinor} />
                      <Text variant="bodySm">Feature Engineering</Text>
                    </InlineStack>
                    <InlineStack gap="200">
                      <Icon source={DataVisualizationMinor} />
                      <Text variant="bodySm">Real-Time Analysis</Text>
                    </InlineStack>
                  </BlockStack>
                </Card>
              </Layout.Section>
            </Layout>
          </BlockStack>
        </Card>
      </Layout.Section>
    </Layout>
  );

  const renderTabContent = () => {
    switch (selectedTab) {
      case 0:
        return renderOverview();
      case 1:
        return renderStreams();
      case 2:
        return renderJobs();
      case 3:
        return renderInsights();
      default:
        return renderOverview();
    }
  };

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

  return (
    <Page>
      <TitleBar title="BetterBundle - Modern Dashboard" />
      
      <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
        {renderTabContent()}
      </Tabs>

      {/* Stream Details Modal */}
      <Modal
        open={showStreamModal}
        onClose={() => setShowStreamModal(false)}
        title="Redis Stream Details"
        primaryAction={{
          content: "Close",
          onAction: () => setShowStreamModal(false),
        }}
      >
        <Modal.Section>
          <BlockStack gap="400">
            <Text as="p">
              Detailed information about each Redis stream and its current status.
            </Text>
            {streamStatus.map((stream, index) => (
              <Card key={index} padding="400">
                <BlockStack gap="200">
                  <Text variant="headingSm" as="h4">
                    {stream.name}
                  </Text>
                  <InlineStack gap="400">
                    <Badge tone={stream.status === "active" ? "success" : "info"}>
                      {stream.status}
                    </Badge>
                    <Text variant="bodySm">
                      {stream.count} messages
                    </Text>
                  </InlineStack>
                  <Text variant="bodySm" tone="subdued">
                    Last activity: {stream.lastActivity}
                  </Text>
                </BlockStack>
              </Card>
            ))}
          </BlockStack>
        </Modal.Section>
      </Modal>
    </Page>
  );
}
