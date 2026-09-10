import { useEffect, useRef, useState, useCallback } from "react";
import {
  Banner,
  BlockStack,
  Button,
  Modal,
  ProgressBar,
  Spinner,
  Text,
} from "@shopify/polaris";

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
    <Modal
      open
      // No onClose: this is a blocking setup step, not a dismissible dialog.
      // The merchant leaves it by finishing, retrying, or the timeout button.
      onClose={() => {}}
      title={
        stage === "complete"
          ? "Your recommendations are ready"
          : stage === "error"
            ? "Analysis didn't finish"
            : stage === "timeout"
              ? "This is taking longer than usual"
              : "Setting up your recommendations"
      }
      {...(stage === "timeout"
        ? { primaryAction: { content: "Continue anyway", onAction: onComplete } }
        : {})}
      {...(stage === "error"
        ? {
            primaryAction: {
              content: "Retry analysis",
              loading: retriggering,
              onAction: handleRetrigger,
            },
          }
        : {})}
    >
      <Modal.Section>
        <BlockStack gap="400" inlineAlign="center">
          {stage !== "complete" && stage !== "error" && (
            <Spinner accessibilityLabel="Analysing your catalogue" size="large" />
          )}

          <Text as="p" alignment="center" tone="subdued">
            {stage === "complete"
              ? "We've analysed your catalogue and built your recommendations."
              : stage === "timeout"
                ? "You can carry on — analysis will keep running in the background."
                : detail ||
                  "We're analysing your catalogue and order history to build personalised recommendations. This usually takes a few minutes."}
          </Text>

          {stage !== "error" && stage !== "timeout" && (
            <BlockStack gap="100" inlineAlign="center">
              <ProgressBar
                progress={Math.round(progress * 100)}
                size="small"
                tone={stage === "complete" ? "success" : "primary"}
              />
              <Text as="span" variant="bodySm" tone="subdued">
                {stage === "complete" ? "100%" : `${Math.round(progress * 100)}%`}
              </Text>
            </BlockStack>
          )}

          {stage === "error" && (
            <Banner tone="critical">
              <Text as="p">
                {detail || "Something went wrong during analysis."}
              </Text>
            </Banner>
          )}
        </BlockStack>
      </Modal.Section>
    </Modal>
  );
}
