import { useState, useCallback, useEffect, useRef } from "react";
import { useFetcher } from "@remix-run/react";
import type { AnalysisState, ErrorState } from "../types";
import { PROGRESS_CONFIG } from "../constants";

export function useAnalysis(initialJob?: {
  jobId: string;
  status: string;
  progress: number;
}) {
  const [state, setState] = useState<AnalysisState>(
    initialJob ? "loading" : "idle",
  );
  const [progress, setProgress] = useState(initialJob?.progress || 0);
  const [error, setError] = useState<ErrorState | null>(null);
  const [hasStartedAnalysis, setHasStartedAnalysis] = useState(!!initialJob);
  const [jobId, setJobId] = useState<string | null>(initialJob?.jobId || null);
  const [jobStatus, setJobStatus] = useState<any>(null);

  const analysisFetcher = useFetcher<any>();
  const statusFetcher = useFetcher<any>();

  // Start analysis with validation
  const startAnalysis = useCallback(() => {
    if (hasStartedAnalysis) return; // Prevent multiple submissions

    setState("checking");
    setProgress(5);
    setError(null);
    setHasStartedAnalysis(true);
    setJobId(null);
    setJobStatus(null);

    // Submit analysis job
    analysisFetcher.submit(
      {},
      { method: "POST", action: "/api/analysis/start" },
    );
  }, [analysisFetcher, hasStartedAnalysis]);

  // Handle analysis job submission response
  useEffect(() => {
    if (analysisFetcher.state === "idle" && analysisFetcher.data) {
      console.log("🚀 Analysis start response:", analysisFetcher.data);

      if (analysisFetcher.data.success) {
        if (analysisFetcher.data.jobId) {
          // Job was queued successfully
          setJobId(analysisFetcher.data.jobId);
          setState("loading");
          setProgress(10);

          // Show success message and wait for notification
          console.log("🚀 Analysis job started:", analysisFetcher.data.jobId);
        } else {
          // Immediate success (fallback)
          setState("success");
          setHasStartedAnalysis(false);
        }
      } else {
        // Analysis failed
        setState("error");
        setHasStartedAnalysis(false);
        setError({
          title: "Analysis Failed",
          description: analysisFetcher.data.error || "Unknown analysis error",
          action: {
            content: "Try Again",
            onAction: startAnalysis,
          },
          recommendations: [
            "Check your internet connection",
            "Ensure your store has sufficient data",
            "Try again in a few minutes",
          ],
        });
      }
    }
  }, [analysisFetcher.state, analysisFetcher.data, startAnalysis]);

  // Poll for job status when we have a jobId
  // Strategy: Poll every 15 seconds with better error handling and timeout logic
  useEffect(() => {
    if (!jobId) return;

    let pollCount = 0;
    const maxPolls = 120; // Stop after 30 minutes (120 * 15 seconds)
    let stuckInQueuedCount = 0;
    const maxStuckInQueued = 20; // Stop if stuck in queued for 5 minutes (20 * 15 seconds)

    const pollStatus = () => {
      statusFetcher.load(`/api/analysis/status?jobId=${jobId}`);
    };

    // Poll immediately
    pollStatus();

    // Set up polling interval
    const interval = setInterval(() => {
      pollCount++;

      // Stop polling if we've hit the maximum number of polls
      if (pollCount >= maxPolls) {
        console.log("⏰ Stopping job status polling after 30 minutes");
        clearInterval(interval);
        if (state === "loading") {
          setState("error");
          setHasStartedAnalysis(false);
          setError({
            title: "Analysis Timeout",
            description:
              "The analysis is taking longer than expected. Please try again.",
            action: { content: "Try Again", onAction: startAnalysis },
            recommendations: [
              "The analysis may be processing a large amount of data",
              "Try again in a few minutes",
              "Contact support if the issue persists",
            ],
          });
        }
        return;
      }

      // Check if job is stuck in queued status
      if (statusFetcher.data?.job?.status === "queued") {
        stuckInQueuedCount++;
        if (stuckInQueuedCount >= maxStuckInQueued) {
          console.log(
            "⚠️ Job stuck in queued status for too long, stopping polling",
          );
          clearInterval(interval);
          setState("error");
          setHasStartedAnalysis(false);
          setError({
            title: "Analysis Stuck",
            description:
              "The analysis job is stuck in queue. This might be due to a system issue.",
            action: { content: "Try Again", onAction: startAnalysis },
            recommendations: [
              "The worker might be down or overloaded",
              "Try again in a few minutes",
              "Contact support if the issue persists",
            ],
          });
          return;
        }
      } else {
        // Reset stuck counter if job is not in queued status
        stuckInQueuedCount = 0;
      }

      // Only poll if the previous request was successful or hasn't been made yet
      if (!statusFetcher.data || statusFetcher.data.success !== false) {
        pollStatus();
      } else {
        // If we get authentication errors, stop polling
        console.log("🔐 Authentication error detected, stopping polling");
        clearInterval(interval);
        setState("error");
        setHasStartedAnalysis(false);
        setError({
          title: "Authentication Error",
          description:
            "Unable to check analysis status due to authentication issues.",
          action: { content: "Try Again", onAction: startAnalysis },
          recommendations: [
            "Try refreshing the page",
            "Check if your session is still valid",
            "Contact support if the issue persists",
          ],
        });
      }
    }, 15000); // Poll every 15 seconds

    return () => {
      clearInterval(interval);
    };
  }, [jobId, statusFetcher, state, startAnalysis]);

  // Handle status updates
  useEffect(() => {
    if (statusFetcher.state === "idle" && statusFetcher.data) {
      console.log("📊 Status update:", statusFetcher.data);

      if (statusFetcher.data.success && statusFetcher.data.job) {
        const job = statusFetcher.data.job;
        setJobStatus(job);
        setProgress(job.progress || 0);

        if (job.status === "completed") {
          setState("success");
          setHasStartedAnalysis(false);
          setJobId(null); // Clear jobId to stop polling
          console.log("✅ Analysis completed successfully");
        } else if (job.status === "failed") {
          setState("error");
          setHasStartedAnalysis(false);
          setJobId(null); // Clear jobId to stop polling
          setError({
            title: "Analysis Failed",
            description: job.error || "The analysis failed during processing",
            action: {
              content: "Try Again",
              onAction: startAnalysis,
            },
            recommendations: [
              "Check your store has sufficient data (orders and products)",
              "Ensure your store is accessible",
              "Try again in a few minutes",
              "Contact support if the issue persists",
            ],
          });
          console.log("❌ Analysis failed:", job.error);
        } else if (job.status === "processing") {
          setState("loading");
          console.log("🔄 Analysis in progress:", job.progress + "%");
        }
      }
    }
  }, [statusFetcher.state, statusFetcher.data, startAnalysis]);

  const handleRetry = useCallback(() => {
    setState("idle");
    setError(null);
    setHasStartedAnalysis(false);
    setJobId(null); // This will stop polling
    setJobStatus(null);
    setProgress(0);
  }, []);

  return {
    state,
    progress,
    error,
    jobId,
    jobStatus,
    startAnalysis,
    handleRetry,
    isLoading:
      analysisFetcher.state !== "idle" || statusFetcher.state !== "idle",
    isSubmitting: analysisFetcher.state === "submitting",
  };
}
