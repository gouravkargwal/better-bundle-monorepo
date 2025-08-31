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
  // Strategy: Poll every 15 seconds with 30-minute maximum to prevent infinite polling
  useEffect(() => {
    if (!jobId) return;

    const pollStatus = () => {
      statusFetcher.load(`/api/analysis/status?jobId=${jobId}`);
    };

    // Poll immediately
    pollStatus();

    // Set up polling interval - 15 seconds is a good balance between responsiveness and server load
    // But stop polling if authentication fails
    const interval = setInterval(() => {
      // Only poll if the previous request was successful or hasn't been made yet
      if (!statusFetcher.data || statusFetcher.data.success !== false) {
        pollStatus();
      }
    }, 15000); // Poll every 15 seconds

    // Stop polling after 30 minutes to prevent infinite polling
    const maxDuration = setTimeout(
      () => {
        console.log("⏰ Stopping job status polling after 30 minutes");
        clearInterval(interval);
        // Set error state if still loading
        if (state === "loading") {
          setState("error");
          setHasStartedAnalysis(false);
          setError({
            title: "Analysis Timeout",
            description:
              "The analysis is taking longer than expected. Please try again.",
            action: {
              content: "Try Again",
              onAction: startAnalysis,
            },
            recommendations: [
              "The analysis may be processing a large amount of data",
              "Try again in a few minutes",
              "Contact support if the issue persists",
            ],
          });
        }
      },
      30 * 60 * 1000,
    ); // 30 minutes

    return () => {
      clearInterval(interval);
      clearTimeout(maxDuration);
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
