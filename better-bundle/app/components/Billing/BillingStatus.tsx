import {
  Banner,
  BlockStack,
  ProgressBar,
  Text,
  InlineStack,
  Icon,
  Card,
} from "@shopify/polaris";
import {
  CashDollarIcon,
  StarFilledIcon,
  AlertTriangleIcon,
  CheckCircleIcon,
} from "@shopify/polaris-icons";

export function BillingStatus({
  billingData,
  formatCurrency,
  getStatusBadge,
  formatDate,
}: any) {
  if (!billingData?.billing_plan) {
    return (
      <Banner tone="warning">
        <Text as="p">No billing plan found. Please contact support.</Text>
      </Banner>
    );
  }

  const plan = billingData.billing_plan;
  const trialStatus = plan.trial_status;

  // Ensure trial status values are numbers
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

  return (
    <BlockStack gap="400">
      {/* Billing Plan Hero Section */}
      <div
        style={{
          padding: "24px 20px",
          background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
          borderRadius: "16px",
          color: "white",
          textAlign: "center",
          position: "relative",
          overflow: "hidden",
          boxShadow:
            "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
          border: "1px solid rgba(255, 255, 255, 0.1)",
        }}
      >
        <div style={{ position: "relative", zIndex: 2 }}>
          {/* Hero Badge */}
          <div style={{ marginBottom: "12px" }}>
            <div
              style={{
                display: "inline-block",
                padding: "6px 12px",
                backgroundColor: "rgba(255, 255, 255, 0.2)",
                border: "1px solid rgba(255, 255, 255, 0.3)",
                color: "white",
                fontWeight: "600",
                borderRadius: "6px",
                fontSize: "12px",
              }}
            >
              💳 Billing Plan
            </div>
          </div>

          {/* Main Headline */}
          <div
            style={{
              fontSize: "2rem",
              lineHeight: "1.2",
              marginBottom: "8px",
              background: "linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
              fontWeight: "bold",
            }}
          >
            {plan.name}
          </div>

          {/* Subheadline */}
          <div
            style={{
              marginBottom: "12px",
              maxWidth: "500px",
              margin: "0 auto 12px",
            }}
          >
            <div
              style={{
                color: "rgba(255,255,255,0.95)",
                lineHeight: "1.4",
                fontWeight: "500",
                fontSize: "1rem",
              }}
            >
              {plan.type.replace("_", " ").toUpperCase()} Plan •{" "}
              {getStatusBadge(plan.status)}
            </div>
          </div>

          {/* Key Benefits Row */}
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              gap: "16px",
              marginBottom: "16px",
              flexWrap: "wrap",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div
                style={{
                  width: "8px",
                  height: "8px",
                  backgroundColor: "#10B981",
                  borderRadius: "50%",
                }}
              />
              <span
                style={{
                  color: "rgba(255,255,255,0.9)",
                  fontSize: "1.125rem",
                }}
              >
                Effective: {formatDate(plan.effective_from)}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div
                style={{
                  width: "8px",
                  height: "8px",
                  backgroundColor: "#10B981",
                  borderRadius: "50%",
                }}
              />
              <span
                style={{
                  color: "rgba(255,255,255,0.9)",
                  fontSize: "1.125rem",
                }}
              >
                Currency: {plan.currency || "USD"}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div
                style={{
                  width: "8px",
                  height: "8px",
                  backgroundColor: "#10B981",
                  borderRadius: "50%",
                }}
              />
              <span
                style={{
                  color: "rgba(255,255,255,0.9)",
                  fontSize: "1.125rem",
                }}
              >
                Rate: 3%
              </span>
            </div>
          </div>

          {/* Enhanced Decorative elements */}
          <div
            style={{
              position: "absolute",
              top: "-50px",
              right: "-50px",
              width: "150px",
              height: "150px",
              background:
                "radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)",
              borderRadius: "50%",
              zIndex: 1,
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: "-40px",
              left: "-40px",
              width: "120px",
              height: "120px",
              background:
                "radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 70%)",
              borderRadius: "50%",
              zIndex: 1,
            }}
          />
        </div>
      </div>

      {/* Trial Status */}
      {safeTrialStatus.is_trial_active ? (
        <BlockStack gap="400">
          <div
            style={{
              padding: "24px",
              backgroundColor: "#F8FAFC",
              borderRadius: "12px",
              border: "1px solid #E2E8F0",
            }}
          >
            <div style={{ color: "#1E293B" }}>
              <Text as="h2" variant="headingLg" fontWeight="bold">
                Free Trial Active
              </Text>
            </div>
            <div style={{ marginTop: "8px" }}>
              <Text as="p" variant="bodyMd" tone="subdued">
                Track your trial progress and remaining revenue needed
              </Text>
            </div>
          </div>

          <div
            style={{
              padding: "24px",
              backgroundColor: "#F8FAFC",
              borderRadius: "12px",
              border: "1px solid #E2E8F0",
            }}
          >
            <BlockStack gap="300">
              <InlineStack align="space-between" blockAlign="center">
                <Text as="h3" variant="headingMd">
                  Trial Progress
                </Text>
                <Text as="p" variant="bodyMd" tone="subdued">
                  {Math.round(safeTrialStatus.trial_progress)}% Complete
                </Text>
              </InlineStack>

              <ProgressBar
                progress={safeTrialStatus.trial_progress}
                size="large"
              />

              <Text as="p" variant="bodyMd" tone="subdued">
                Generate{" "}
                {formatCurrency(
                  safeTrialStatus.remaining_revenue,
                  plan.currency,
                )}{" "}
                more in attributed revenue to start billing
              </Text>
            </BlockStack>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "16px",
            }}
          >
            <div
              style={{
                transition: "all 0.2s ease-in-out",
                cursor: "pointer",
                borderRadius: "8px",
                overflow: "hidden",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-4px)";
                e.currentTarget.style.boxShadow =
                  "0 12px 30px rgba(0,0,0,0.15)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <Card>
                <div style={{ minHeight: "120px", padding: "4px" }}>
                  <BlockStack gap="300">
                    <InlineStack align="space-between" blockAlign="center">
                      <BlockStack gap="100">
                        <Text
                          as="h3"
                          variant="headingSm"
                          tone="subdued"
                          fontWeight="medium"
                        >
                          Current Revenue
                        </Text>
                      </BlockStack>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          minWidth: "40px",
                          minHeight: "40px",
                          padding: "12px",
                          backgroundColor: "#10B98115",
                          borderRadius: "16px",
                          border: "2px solid #10B98130",
                        }}
                      >
                        <Icon source={CashDollarIcon} tone="base" />
                      </div>
                    </InlineStack>

                    <InlineStack align="space-between" blockAlign="center">
                      <div style={{ color: "#10B981" }}>
                        <Text as="p" variant="headingLg" fontWeight="bold">
                          {formatCurrency(
                            safeTrialStatus.trial_revenue,
                            plan.currency,
                          )}
                        </Text>
                      </div>
                    </InlineStack>
                  </BlockStack>
                </div>
              </Card>
            </div>

            <div
              style={{
                transition: "all 0.2s ease-in-out",
                cursor: "pointer",
                borderRadius: "8px",
                overflow: "hidden",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-4px)";
                e.currentTarget.style.boxShadow =
                  "0 12px 30px rgba(0,0,0,0.15)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <Card>
                <div style={{ minHeight: "120px", padding: "4px" }}>
                  <BlockStack gap="300">
                    <InlineStack align="space-between" blockAlign="center">
                      <BlockStack gap="100">
                        <Text
                          as="h3"
                          variant="headingSm"
                          tone="subdued"
                          fontWeight="medium"
                        >
                          Trial Threshold
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          (Equivalent to $200 USD)
                        </Text>
                      </BlockStack>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          minWidth: "40px",
                          minHeight: "40px",
                          padding: "12px",
                          backgroundColor: "#3B82F615",
                          borderRadius: "16px",
                          border: "2px solid #3B82F630",
                        }}
                      >
                        <Icon source={StarFilledIcon} tone="base" />
                      </div>
                    </InlineStack>

                    <InlineStack align="space-between" blockAlign="center">
                      <div style={{ color: "#3B82F6" }}>
                        <Text as="p" variant="headingLg" fontWeight="bold">
                          {formatCurrency(
                            safeTrialStatus.trial_threshold,
                            plan.currency,
                          )}
                        </Text>
                      </div>
                    </InlineStack>
                  </BlockStack>
                </div>
              </Card>
            </div>

            <div
              style={{
                transition: "all 0.2s ease-in-out",
                cursor: "pointer",
                borderRadius: "8px",
                overflow: "hidden",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-4px)";
                e.currentTarget.style.boxShadow =
                  "0 12px 30px rgba(0,0,0,0.15)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <Card>
                <div style={{ minHeight: "120px", padding: "4px" }}>
                  <BlockStack gap="300">
                    <InlineStack align="space-between" blockAlign="center">
                      <BlockStack gap="100">
                        <Text
                          as="h3"
                          variant="headingSm"
                          tone="subdued"
                          fontWeight="medium"
                        >
                          Remaining
                        </Text>
                      </BlockStack>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          minWidth: "40px",
                          minHeight: "40px",
                          padding: "12px",
                          backgroundColor: "#F59E0B15",
                          borderRadius: "16px",
                          border: "2px solid #F59E0B30",
                        }}
                      >
                        <Icon source={AlertTriangleIcon} tone="base" />
                      </div>
                    </InlineStack>

                    <InlineStack align="space-between" blockAlign="center">
                      <div style={{ color: "#F59E0B" }}>
                        <Text as="p" variant="headingLg" fontWeight="bold">
                          {formatCurrency(
                            safeTrialStatus.remaining_revenue,
                            plan.currency,
                          )}
                        </Text>
                      </div>
                    </InlineStack>
                  </BlockStack>
                </div>
              </Card>
            </div>
          </div>
        </BlockStack>
      ) : (
        <BlockStack gap="400">
          <div
            style={{
              padding: "24px",
              backgroundColor: "#F8FAFC",
              borderRadius: "12px",
              border: "1px solid #E2E8F0",
            }}
          >
            <div style={{ color: "#1E293B" }}>
              <Text as="h2" variant="headingLg" fontWeight="bold">
                Trial Completed - Billing Active
              </Text>
            </div>
            <div style={{ marginTop: "8px" }}>
              <Text as="p" variant="bodyMd" tone="subdued">
                Your trial has ended. You're now being charged 3% of attributed
                revenue.
              </Text>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "16px",
            }}
          >
            <div
              style={{
                transition: "all 0.2s ease-in-out",
                cursor: "pointer",
                borderRadius: "8px",
                overflow: "hidden",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-4px)";
                e.currentTarget.style.boxShadow =
                  "0 12px 30px rgba(0,0,0,0.15)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <Card>
                <div style={{ minHeight: "120px", padding: "4px" }}>
                  <BlockStack gap="300">
                    <InlineStack align="space-between" blockAlign="center">
                      <BlockStack gap="100">
                        <Text
                          as="h3"
                          variant="headingSm"
                          tone="subdued"
                          fontWeight="medium"
                        >
                          Trial Revenue
                        </Text>
                      </BlockStack>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          minWidth: "40px",
                          minHeight: "40px",
                          padding: "12px",
                          backgroundColor: "#10B98115",
                          borderRadius: "16px",
                          border: "2px solid #10B98130",
                        }}
                      >
                        <Icon source={CashDollarIcon} tone="base" />
                      </div>
                    </InlineStack>

                    <InlineStack align="space-between" blockAlign="center">
                      <div style={{ color: "#10B981" }}>
                        <Text as="p" variant="headingLg" fontWeight="bold">
                          {formatCurrency(
                            safeTrialStatus.trial_revenue,
                            plan.currency,
                          )}
                        </Text>
                      </div>
                    </InlineStack>
                  </BlockStack>
                </div>
              </Card>
            </div>

            <div
              style={{
                transition: "all 0.2s ease-in-out",
                cursor: "pointer",
                borderRadius: "8px",
                overflow: "hidden",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-4px)";
                e.currentTarget.style.boxShadow =
                  "0 12px 30px rgba(0,0,0,0.15)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <Card>
                <div style={{ minHeight: "120px", padding: "4px" }}>
                  <BlockStack gap="300">
                    <InlineStack align="space-between" blockAlign="center">
                      <BlockStack gap="100">
                        <Text
                          as="h3"
                          variant="headingSm"
                          tone="subdued"
                          fontWeight="medium"
                        >
                          Billing Rate
                        </Text>
                      </BlockStack>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          minWidth: "40px",
                          minHeight: "40px",
                          padding: "12px",
                          backgroundColor: "#3B82F615",
                          borderRadius: "16px",
                          border: "2px solid #3B82F630",
                        }}
                      >
                        <Icon source={StarFilledIcon} tone="base" />
                      </div>
                    </InlineStack>

                    <InlineStack align="space-between" blockAlign="center">
                      <div style={{ color: "#3B82F6" }}>
                        <Text as="p" variant="headingLg" fontWeight="bold">
                          3%
                        </Text>
                      </div>
                    </InlineStack>
                  </BlockStack>
                </div>
              </Card>
            </div>

            <div
              style={{
                transition: "all 0.2s ease-in-out",
                cursor: "pointer",
                borderRadius: "8px",
                overflow: "hidden",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-4px)";
                e.currentTarget.style.boxShadow =
                  "0 12px 30px rgba(0,0,0,0.15)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <Card>
                <div style={{ minHeight: "120px", padding: "4px" }}>
                  <BlockStack gap="300">
                    <InlineStack align="space-between" blockAlign="center">
                      <BlockStack gap="100">
                        <Text
                          as="h3"
                          variant="headingSm"
                          tone="subdued"
                          fontWeight="medium"
                        >
                          Status
                        </Text>
                      </BlockStack>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          minWidth: "40px",
                          minHeight: "40px",
                          padding: "12px",
                          backgroundColor: "#10B98115",
                          borderRadius: "16px",
                          border: "2px solid #10B98130",
                        }}
                      >
                        <Icon source={CheckCircleIcon} tone="base" />
                      </div>
                    </InlineStack>

                    <InlineStack align="space-between" blockAlign="center">
                      <div style={{ color: "#10B981" }}>
                        <Text as="p" variant="headingLg" fontWeight="bold">
                          Active
                        </Text>
                      </div>
                    </InlineStack>
                  </BlockStack>
                </div>
              </Card>
            </div>
          </div>
        </BlockStack>
      )}
    </BlockStack>
  );
}
