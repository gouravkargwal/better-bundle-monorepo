import { useEffect, useRef, useState, useCallback } from "react";
import { Text, Button, Banner } from "@shopify/polaris";

interface AnalysisModalProps {
  /** Whether AI is already known to be ready from loader data */
  initiallyReady: boolean;
  /** Called when AI finishes or user dismisses (for timeout) */
  onComplete: () => void;
}

type Stage = "analyzing" | "training" | "timeout" | "complete" | "error";

const POLL_MS = 3_000;
const MAX_POLLS = 100;

export function AnalysisModal({
  initiallyReady,
  onComplete,
}: AnalysisModalProps) {
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState<Stage>("analyzing");
  const [detail, setDetail] = useState("Analyzing your product catalog...");
  const [retriggering, setRetriggering] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const countRef = useRef(0);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const poll = useCallback(async () => {
    countRef.current++;
    try {
      const resp = await fetch("/api/onboarding/analysis-progress");
      if (!resp.ok) {
        setDetail("Waiting for analysis pipeline...");
        return;
      }
      const data = await resp.json();
      setProgress(data.progress ?? 0);
      setDetail(data.detail ?? "");

      if (data.stage === "complete") {
        setStage("complete");
        setProgress(1);
        stopPolling();
        // Give user a moment to see the completion, then dismiss
        setTimeout(onComplete, 800);
        return;
      }

      if (data.stage === "training") {
        setStage("training");
      }

      if (data.stage === "error") {
        setStage("error");
        setDetail(data.detail ?? "An error occurred during analysis");
        stopPolling();
        return;
      }

      // Timeout
      if (countRef.current >= MAX_POLLS) {
        setStage("timeout");
        stopPolling();
      }
    } catch {
      setDetail("Waiting for analysis pipeline...");
      // Only timeout if we've exhausted max polls
      if (countRef.current >= MAX_POLLS) {
        setStage("timeout");
        stopPolling();
      }
    }
  }, [onComplete, stopPolling]);

  useEffect(() => {
    if (initiallyReady) {
      onComplete();
      return;
    }

    // Start polling
    poll(); // immediate first poll
    pollRef.current = setInterval(poll, POLL_MS);

    return () => stopPolling();
  }, [initiallyReady, onComplete, poll, stopPolling]);

  const handleRetrigger = useCallback(async () => {
    setRetriggering(true);
    try {
      await fetch("/api/onboarding/retrigger-analysis", { method: "POST" });
    } catch {
      // ignore
    }
    // Reset and start polling again
    countRef.current = 0;
    setStage("analyzing");
    setProgress(0);
    setDetail("Restarting analysis...");
    setRetriggering(false);
    pollRef.current = setInterval(poll, POLL_MS);
  }, [poll]);

  const showRetry = stage === "error";

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(255, 255, 255, 0.92)",
        backdropFilter: "blur(4px)",
      }}
    >
      <div
        style={{
          maxWidth: "420px",
          width: "90%",
          padding: "clamp(24px, 4vw, 48px)",
          textAlign: "center",
        }}
      >
        {/* Animated icon */}
        <div
          style={{
            width: "64px",
            height: "64px",
            borderRadius: "50%",
            background:
              stage === "complete"
                ? "linear-gradient(135deg, #10B981, #059669)"
                : stage === "error"
                  ? "linear-gradient(135deg, #EF4444, #DC2626)"
                  : "linear-gradient(135deg, #667eea, #764ba2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 20px",
            animation:
              stage === "complete" || stage === "error"
                ? undefined
                : "modalPulse 1.5s ease-in-out infinite",
            boxShadow:
              stage === "complete"
                ? "0 4px 20px rgba(16, 185, 129, 0.3)"
                : stage === "error"
                  ? "0 4px 20px rgba(239, 68, 68, 0.3)"
                  : "0 4px 20px rgba(102, 126, 234, 0.3)",
            transition: "all 0.3s ease",
          }}
        >
          <span style={{ color: "white", fontSize: "28px" }}>
            {stage === "complete" ? "✓" : stage === "error" ? "✗" : "⚡"}
          </span>
        </div>

        {/* Title */}
        <Text as="h2" variant="headingLg" fontWeight="bold" tone="base">
          {stage === "complete"
            ? "AI Recommendations Ready!"
            : stage === "error"
              ? "Analysis Failed"
              : "Setting Up AI Recommendations"}
        </Text>

        {/* Description */}
        <div style={{ marginTop: "8px" }}>
          <Text as="p" variant="bodyMd" tone="subdued">
            {stage === "complete"
              ? "Your store's AI is trained and ready to recommend."
              : stage === "timeout"
                ? "Analysis is taking longer than expected. You can continue setting up."
                : stage === "error"
                  ? detail
                  : detail}
          </Text>
        </div>

        {/* Progress bar */}
        {stage !== "error" && (
          <div style={{ marginTop: "24px" }}>
            <div
              style={{
                height: "6px",
                backgroundColor: "rgba(102, 126, 234, 0.15)",
                borderRadius: "3px",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${Math.round(progress * 100)}%`,
                  background:
                    stage === "complete"
                      ? "linear-gradient(90deg, #10B981, #059669)"
                      : "linear-gradient(90deg, #667eea, #764ba2)",
                  borderRadius: "3px",
                  transition: "width 0.5s ease",
                }}
              />
            </div>
            <div style={{ marginTop: "8px" }}>
              <Text as="p" variant="bodySm" tone="subdued">
                {stage === "complete"
                  ? "100%"
                  : stage === "timeout"
                    ? ""
                    : `${Math.round(progress * 100)}%`}
              </Text>
            </div>
          </div>
        )}

        {/* Error banner with retry */}
        {showRetry && (
          <div style={{ marginTop: "20px" }}>
            <Banner tone="critical">
              <Text as="p" variant="bodyMd" tone="critical">
                {detail || "Something went wrong during analysis."}
              </Text>
            </Banner>
            <div style={{ marginTop: "16px" }}>
              <Button
                variant="primary"
                loading={retriggering}
                onClick={handleRetrigger}
              >
                Retry Analysis
              </Button>
            </div>
          </div>
        )}

        {/* Timeout action */}
        {stage === "timeout" && (
          <div style={{ marginTop: "20px" }}>
            <Button variant="primary" onClick={onComplete}>
              Continue to Dashboard
            </Button>
          </div>
        )}

        {/* Trial reminder */}
        <div style={{ marginTop: "20px" }}>
          <Text as="p" variant="bodySm" tone="subdued">
            14-day free trial · Cancel anytime
          </Text>
        </div>
      </div>

      <style>{`
        @keyframes modalPulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.06); }
        }
      `}</style>
    </div>
  );
}
