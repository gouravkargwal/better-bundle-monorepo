/**
 * Trial Testing Dashboard
 *
 * Provides a UI for manually testing the $200 trial flow
 */

import React, { useState, useEffect } from "react";
import {
  Card,
  Text,
  BlockStack,
  InlineStack,
  Button,
  Banner,
  TextField,
  Select,
  ProgressBar,
  Badge,
  Divider,
  List,
  Box,
  Icon,
} from "@shopify/polaris";
import {
  CheckCircleIcon,
  AlertCircleIcon,
  PlayIcon,
  RefreshIcon,
} from "@shopify/polaris-icons";

interface TrialTestDashboardProps {
  shop: string;
  initialStatus?: any;
}

export function TrialTestDashboard({
  shop,
  initialStatus,
}: TrialTestDashboardProps) {
  const [trialStatus, setTrialStatus] = useState(initialStatus);
  const [isLoading, setIsLoading] = useState(false);
  const [testResults, setTestResults] = useState<any>(null);
  const [revenueAmount, setRevenueAmount] = useState("50");
  const [selectedCurrency, setSelectedCurrency] = useState("USD");
  const [testHistory, setTestHistory] = useState<any[]>([]);

  const currencies = [
    { label: "USD", value: "USD" },
    { label: "EUR", value: "EUR" },
    { label: "GBP", value: "GBP" },
    { label: "CAD", value: "CAD" },
    { label: "AUD", value: "AUD" },
  ];

  const testTypes = [
    { label: "Create Trial", value: "create_trial" },
    { label: "Add Revenue", value: "add_revenue" },
    { label: "Complete Flow", value: "complete_flow" },
    { label: "Edge Cases", value: "edge_cases" },
    { label: "Currency Support", value: "currency_support" },
    { label: "Run All Tests", value: "run_all_tests" },
  ];

  useEffect(() => {
    if (initialStatus) {
      setTrialStatus(initialStatus);
    }
  }, [initialStatus]);

  const executeTest = async (testType: string, additionalData?: any) => {
    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append("testType", testType);

      if (additionalData) {
        Object.entries(additionalData).forEach(([key, value]) => {
          formData.append(key, value.toString());
        });
      }

      const response = await fetch("/api/test/trial", {
        method: "POST",
        body: formData,
      });

      const result = await response.json();

      if (result.success) {
        setTestResults(result.result);
        setTestHistory((prev) => [
          ...prev,
          {
            testType,
            timestamp: new Date().toISOString(),
            result: result.result,
          },
        ]);

        // Refresh status if it's a status-changing test
        if (
          ["create_trial", "add_revenue", "complete_with_consent"].includes(
            testType,
          )
        ) {
          await refreshStatus();
        }
      } else {
        setTestResults({ error: result.error });
      }
    } catch (error) {
      console.error("Error executing test:", error);
      setTestResults({ error: error.message });
    } finally {
      setIsLoading(false);
    }
  };

  const refreshStatus = async () => {
    try {
      const response = await fetch("/api/test/trial");
      const data = await response.json();

      if (data.success) {
        setTrialStatus(data.trialStatus);
      }
    } catch (error) {
      console.error("Error refreshing status:", error);
    }
  };

  const getStatusBadge = (status: any) => {
    if (status.isTrialActive) {
      return <Badge tone="info">Trial Active</Badge>;
    } else if (status.trialCompleted && status.needsConsent) {
      return <Badge tone="warning">Needs Consent</Badge>;
    } else if (status.trialCompleted && !status.needsConsent) {
      return <Badge tone="success">Completed</Badge>;
    } else {
      return <Badge tone="critical">No Trial</Badge>;
    }
  };

  const getProgressColor = (progress: number) => {
    if (progress < 50) return "info";
    if (progress < 75) return "warning";
    return "success";
  };

  return (
    <BlockStack gap="500">
      {/* Header */}
      <Card sectioned>
        <BlockStack gap="300">
          <InlineStack align="space-between">
            <Text as="h2" variant="headingLg">
              Trial Testing Dashboard
            </Text>
            <Button
              icon={RefreshIcon}
              onClick={refreshStatus}
              loading={isLoading}
            >
              Refresh Status
            </Button>
          </InlineStack>
          <Text as="p" variant="bodyMd">
            Test the $200 revenue-based trial flow for shop:{" "}
            <strong>{shop}</strong>
          </Text>
        </BlockStack>
      </Card>

      {/* Current Status */}
      {trialStatus && (
        <Card sectioned>
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd">
              Current Trial Status
            </Text>

            <InlineStack gap="400" wrap={false}>
              <Box>
                <Text as="p" variant="bodyMd" fontWeight="bold">
                  Status
                </Text>
                {getStatusBadge(trialStatus)}
              </Box>
              <Box>
                <Text as="p" variant="bodyMd" fontWeight="bold">
                  Revenue
                </Text>
                <Text as="p" variant="bodyMd">
                  ${trialStatus.currentRevenue.toFixed(2)} / $
                  {trialStatus.threshold}
                </Text>
              </Box>
              <Box>
                <Text as="p" variant="bodyMd" fontWeight="bold">
                  Progress
                </Text>
                <Text as="p" variant="bodyMd">
                  {trialStatus.progress.toFixed(1)}%
                </Text>
              </Box>
              <Box>
                <Text as="p" variant="bodyMd" fontWeight="bold">
                  Currency
                </Text>
                <Text as="p" variant="bodyMd">
                  {trialStatus.currency}
                </Text>
              </Box>
            </InlineStack>

            {/* Progress Bar */}
            <Box>
              <ProgressBar
                progress={trialStatus.progress}
                size="small"
                tone={getProgressColor(trialStatus.progress)}
              />
            </Box>

            {/* Status Details */}
            <List>
              <List.Item>
                <strong>Trial Active:</strong>{" "}
                {trialStatus.isTrialActive ? "Yes" : "No"}
              </List.Item>
              <List.Item>
                <strong>Trial Completed:</strong>{" "}
                {trialStatus.trialCompleted ? "Yes" : "No"}
              </List.Item>
              <List.Item>
                <strong>Needs Consent:</strong>{" "}
                {trialStatus.needsConsent ? "Yes" : "No"}
              </List.Item>
              <List.Item>
                <strong>Remaining Revenue:</strong> $
                {trialStatus.remainingRevenue.toFixed(2)}
              </List.Item>
            </List>
          </BlockStack>
        </Card>
      )}

      {/* Test Controls */}
      <Card sectioned>
        <BlockStack gap="400">
          <Text as="h3" variant="headingMd">
            Test Controls
          </Text>

          {/* Quick Tests */}
          <BlockStack gap="300">
            <Text as="h4" variant="headingSm">
              Quick Tests
            </Text>
            <InlineStack gap="300" wrap={false}>
              <Button
                icon={PlayIcon}
                onClick={() => executeTest("create_trial")}
                loading={isLoading}
                variant="primary"
              >
                Create Trial
              </Button>
              <Button
                icon={PlayIcon}
                onClick={() => executeTest("get_status")}
                loading={isLoading}
              >
                Get Status
              </Button>
              <Button
                icon={PlayIcon}
                onClick={() => executeTest("complete_with_consent")}
                loading={isLoading}
              >
                Complete with Consent
              </Button>
            </InlineStack>
          </BlockStack>

          <Divider />

          {/* Revenue Test */}
          <BlockStack gap="300">
            <Text as="h4" variant="headingSm">
              Add Revenue
            </Text>
            <InlineStack gap="300" wrap={false}>
              <TextField
                label="Revenue Amount"
                value={revenueAmount}
                onChange={setRevenueAmount}
                type="number"
                suffix="$"
                autoComplete="off"
              />
              <Select
                label="Currency"
                options={currencies}
                value={selectedCurrency}
                onChange={setSelectedCurrency}
              />
              <Button
                icon={PlayIcon}
                onClick={() =>
                  executeTest("add_revenue", {
                    revenueAmount: parseFloat(revenueAmount),
                    currency: selectedCurrency,
                  })
                }
                loading={isLoading}
                variant="primary"
              >
                Add Revenue
              </Button>
            </InlineStack>
          </BlockStack>

          <Divider />

          {/* Advanced Tests */}
          <BlockStack gap="300">
            <Text as="h4" variant="headingSm">
              Advanced Tests
            </Text>
            <InlineStack gap="300" wrap={false}>
              <Button
                icon={PlayIcon}
                onClick={() => executeTest("complete_flow")}
                loading={isLoading}
              >
                Complete Flow
              </Button>
              <Button
                icon={PlayIcon}
                onClick={() => executeTest("edge_cases")}
                loading={isLoading}
              >
                Edge Cases
              </Button>
              <Button
                icon={PlayIcon}
                onClick={() => executeTest("currency_support")}
                loading={isLoading}
              >
                Currency Support
              </Button>
              <Button
                icon={PlayIcon}
                onClick={() => executeTest("run_all_tests")}
                loading={isLoading}
                variant="primary"
              >
                Run All Tests
              </Button>
            </InlineStack>
          </BlockStack>
        </BlockStack>
      </Card>

      {/* Test Results */}
      {testResults && (
        <Card sectioned>
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd">
              Test Results
            </Text>

            {testResults.error ? (
              <Banner tone="critical">
                <Text as="p">
                  <strong>Test Failed:</strong> {testResults.error}
                </Text>
              </Banner>
            ) : (
              <Banner tone="success">
                <Text as="p">
                  <strong>Test Completed Successfully!</strong>
                </Text>
              </Banner>
            )}

            <Box>
              <pre
                style={{
                  backgroundColor: "#f6f6f7",
                  padding: "16px",
                  borderRadius: "4px",
                  overflow: "auto",
                  maxHeight: "400px",
                }}
              >
                {JSON.stringify(testResults, null, 2)}
              </pre>
            </Box>
          </BlockStack>
        </Card>
      )}

      {/* Test History */}
      {testHistory.length > 0 && (
        <Card sectioned>
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd">
              Test History
            </Text>

            <List>
              {testHistory
                .slice(-5)
                .reverse()
                .map((test, index) => (
                  <List.Item key={index}>
                    <InlineStack gap="300" align="space-between">
                      <Text as="p" variant="bodyMd">
                        <strong>{test.testType}</strong> -{" "}
                        {new Date(test.timestamp).toLocaleString()}
                      </Text>
                      <Icon
                        source={
                          test.result.error ? AlertCircleIcon : CheckCircleIcon
                        }
                      />
                    </InlineStack>
                  </List.Item>
                ))}
            </List>
          </BlockStack>
        </Card>
      )}
    </BlockStack>
  );
}
