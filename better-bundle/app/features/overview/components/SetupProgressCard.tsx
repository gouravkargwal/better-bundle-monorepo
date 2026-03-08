import {
  Card,
  Text,
  BlockStack,
  Button,
  InlineStack,
  Badge,
} from "@shopify/polaris";
import { useNavigate } from "@remix-run/react";
import type { SetupStatus } from "../services/overview.types";

interface SetupProgressCardProps {
  setupStatus: SetupStatus;
}

interface Step {
  label: string;
  description: string;
  completed: boolean;
  isCurrent: boolean;
}

export function SetupProgressCard({
  setupStatus,
}: SetupProgressCardProps) {
  const navigate = useNavigate();

  const steps: Step[] = [
    {
      label: "Store connected",
      description: "Your store is linked and billing is set up.",
      completed: setupStatus.storeConnected,
      isCurrent: !setupStatus.storeConnected,
    },
    {
      label: "AI engine ready",
      description: setupStatus.recommendationsReady
        ? `${setupStatus.productsCount} products synced — AI is ready to recommend.`
        : setupStatus.productsAnalyzed
          ? "Products analyzed. AI is training — this usually takes a few minutes."
          : "We're analyzing your product catalog. This usually takes a few minutes.",
      completed: setupStatus.recommendationsReady,
      isCurrent: setupStatus.storeConnected && !setupStatus.recommendationsReady,
    },
    {
      label: "Set up extensions",
      description: setupStatus.setupGuideVisited
        ? "You've visited the extension guide."
        : "Add BetterBundle widgets to your store theme to start showing recommendations.",
      completed: setupStatus.setupGuideVisited,
      isCurrent: setupStatus.recommendationsReady && !setupStatus.setupGuideVisited,
    },
  ];

  const completedCount = steps.filter((s) => s.completed).length;
  const progressPercent = (completedCount / steps.length) * 100;

  return (
    <Card>
      <div style={{ padding: "16px" }}>
        <div
          style={{
            padding: "20px",
            backgroundColor: "#F5F3FF",
            borderRadius: "10px",
            border: "2px solid #8B5CF6",
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* Decorative Elements */}
          <div
            style={{
              position: "absolute",
              top: "-20px",
              right: "-20px",
              width: "80px",
              height: "80px",
              background:
                "radial-gradient(circle, rgba(139,92,246,0.12) 0%, transparent 70%)",
              borderRadius: "50%",
              zIndex: 1,
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: "-15px",
              left: "-15px",
              width: "60px",
              height: "60px",
              background:
                "radial-gradient(circle, rgba(139,92,246,0.08) 0%, transparent 70%)",
              borderRadius: "50%",
              zIndex: 1,
            }}
          />

          <BlockStack gap="400">
            {/* Header */}
            <InlineStack align="space-between" blockAlign="center">
              <BlockStack gap="100">
                <div style={{ color: "#5B21B6" }}>
                  <Text as="h3" variant="headingLg" fontWeight="bold">
                    Setup Progress
                  </Text>
                </div>
                <div style={{ color: "#5B21B6", opacity: 0.8 }}>
                  <Text as="p" variant="bodySm">
                    Complete these steps to start earning
                  </Text>
                </div>
              </BlockStack>
              <Badge
                tone={progressPercent === 100 ? "success" : "info"}
                size="large"
              >
                {`${completedCount}/${steps.length} Complete`}
              </Badge>
            </InlineStack>

            {/* Progress Bar */}
            <div
              style={{
                height: "8px",
                backgroundColor: "rgba(139,92,246,0.15)",
                borderRadius: "4px",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${progressPercent}%`,
                  background:
                    progressPercent === 100
                      ? "linear-gradient(90deg, #10B981, #059669)"
                      : "linear-gradient(90deg, #667eea, #764ba2)",
                  borderRadius: "4px",
                  transition: "width 0.5s ease",
                }}
              />
            </div>

            {/* Steps */}
            <BlockStack gap="200">
              {steps.map((step, index) => (
                <div
                  key={index}
                  style={{
                    display: "flex",
                    gap: "14px",
                    alignItems: "flex-start",
                    padding: step.isCurrent ? "16px" : "10px 12px",
                    backgroundColor: step.isCurrent
                      ? "white"
                      : step.completed
                        ? "rgba(255,255,255,0.5)"
                        : "transparent",
                    borderRadius: "10px",
                    border: step.isCurrent
                      ? "2px solid #DDD6FE"
                      : "1px solid transparent",
                    transition: "all 0.2s ease-in-out",
                  }}
                >
                  {/* Step indicator */}
                  <div
                    style={{
                      width: "32px",
                      height: "32px",
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      background: step.completed
                        ? "linear-gradient(135deg, #10B981, #059669)"
                        : step.isCurrent
                          ? "linear-gradient(135deg, #667eea, #764ba2)"
                          : "rgba(139,92,246,0.12)",
                      color:
                        step.completed || step.isCurrent ? "white" : "#8B5CF6",
                      fontSize: "14px",
                      fontWeight: "700",
                      boxShadow:
                        step.completed || step.isCurrent
                          ? "0 2px 8px rgba(0,0,0,0.15)"
                          : "none",
                    }}
                  >
                    {step.completed ? "\u2713" : index + 1}
                  </div>

                  {/* Step content */}
                  <div style={{ flex: 1 }}>
                    <InlineStack align="space-between" blockAlign="center">
                      <div
                        style={{
                          color: step.completed
                            ? "#065F46"
                            : step.isCurrent
                              ? "#5B21B6"
                              : "#6B7280",
                        }}
                      >
                        <Text
                          as="p"
                          variant="bodyMd"
                          fontWeight={step.isCurrent ? "bold" : "medium"}
                        >
                          {step.label}
                        </Text>
                      </div>
                      {step.completed && (
                        <Badge tone="success" size="small">
                          Done
                        </Badge>
                      )}
                    </InlineStack>

                    {/* Description for current/incomplete steps */}
                    {(step.isCurrent || !step.completed) && (
                      <div style={{ marginTop: "4px" }}>
                        <Text as="p" variant="bodySm" tone="subdued">
                          {step.description}
                        </Text>
                      </div>
                    )}

                    {/* AI engine training spinner */}
                    {step.isCurrent && index === 1 && (
                      <div
                        style={{
                          marginTop: "8px",
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <div
                          style={{
                            width: "16px",
                            height: "16px",
                            border: "2px solid rgba(139,92,246,0.2)",
                            borderTopColor: "#8B5CF6",
                            borderRadius: "50%",
                            animation: "setupSpin 1s linear infinite",
                          }}
                        />
                        <div style={{ color: "#8B5CF6" }}>
                          <Text as="span" variant="bodySm" fontWeight="medium">
                            AI is learning your catalog...
                          </Text>
                        </div>
                      </div>
                    )}

                    {/* Step 3: button to extensions page */}
                    {step.isCurrent && index === 2 && (
                      <div style={{ marginTop: "12px" }}>
                        <Button
                          variant="primary"
                          onClick={() => navigate("/app/extensions")}
                        >
                          Go to Extension Guide
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </BlockStack>
          </BlockStack>

          {/* Spinner animation */}
          <style>{`
            @keyframes setupSpin {
              to { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      </div>
    </Card>
  );
}
