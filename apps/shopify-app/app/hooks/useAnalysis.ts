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

  const handleRetry = useCallback(() => {
    setState("idle");
    setError(null);
    setHasStartedAnalysis(false);
    setJobId(null);
    setJobStatus(null);
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
