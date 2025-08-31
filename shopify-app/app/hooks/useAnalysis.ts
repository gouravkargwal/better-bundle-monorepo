import { useState, useCallback, useEffect, useRef } from "react";
import { useFetcher } from "@remix-run/react";
import type { AnalysisState, ErrorState } from "../types";

export function useAnalysis(initialJob?: {
  jobId: string;
  status: string;
  progress: number;
}) {
  const [state, setState] = useState<AnalysisState>(
    initialJob ? "idle" : "idle",
  );
  const [progress, setProgress] = useState(initialJob?.progress || 0);
  const [error, setError] = useState<ErrorState | null>(null);
  const [hasStartedAnalysis, setHasStartedAnalysis] = useState(!!initialJob);
  const [jobId, setJobId] = useState<string | null>(initialJob?.jobId || null);
  const [jobStatus, setJobStatus] = useState<any>(null);

  const analysisFetcher = useFetcher<any>();
  const statusFetcher = useFetcher<any>();

  // Use refs to track polling state and prevent multiple intervals
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const pollCountRef = useRef(0);
  const stuckInQueuedCountRef = useRef(0);
  const isMountedRef = useRef(true);
  const consecutiveErrorsRef = useRef(0);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      isMountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, []);

  // Start analysis with validation
  const startAnalysis = useCallback(() => {
    console.log("🚀 startAnalysis called!", { hasStartedAnalysis, state });
    
    if (hasStartedAnalysis) {
      console.log("⚠️ Analysis already started, preventing multiple submissions");
      return; // Prevent multiple submissions
    }

    console.log("✅ Starting analysis...");
    
    // Don't set an intermediate state - let the response determine the state
    setError(null);
    setHasStartedAnalysis(true);
    setJobId(null);
    setJobStatus(null);

    // Reset error counters
    consecutiveErrorsRef.current = 0;

    // Submit analysis job
    console.log("📤 Submitting analysis job...");
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
          // Job was queued successfully - go directly to queued state
          setJobId(analysisFetcher.data.jobId);
          setState("queued");
          setProgress(5);

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
  useEffect(() => {
    if (!jobId) {
      // Clear any existing interval when jobId is null
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    // Reset counters for new job
    pollCountRef.current = 0;
    stuckInQueuedCountRef.current = 0;
    consecutiveErrorsRef.current = 0;
    const maxPolls = 120; // Stop after 30 minutes (120 * 15 seconds)
    const maxStuckInQueued = 20; // Stop if stuck in queued for 5 minutes (20 * 15 seconds)

    const pollStatus = () => {
      if (!isMountedRef.current) return;
      statusFetcher.load(`/api/analysis/status?jobId=${jobId}`);
    };

    // Poll immediately
    pollStatus();

    // Set up polling interval
    intervalRef.current = setInterval(() => {
      if (!isMountedRef.current) {
        clearInterval(intervalRef.current!);
        intervalRef.current = null;
        return;
      }

      pollCountRef.current++;

      // Stop polling if we've hit the maximum number of polls
      if (pollCountRef.current >= maxPolls) {
        console.log("⏰ Stopping job status polling after 30 minutes");
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
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
        return;
      }

      // Check if job is stuck in queued status
      if (statusFetcher.data?.job?.status === "queued") {
        stuckInQueuedCountRef.current++;
        if (stuckInQueuedCountRef.current >= maxStuckInQueued) {
          console.log(
            "⚠️ Job stuck in queued status for too long, stopping polling",
          );
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
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
        stuckInQueuedCountRef.current = 0;
      }

      // Only poll if the previous request was successful or hasn't been made yet
      if (!statusFetcher.data || statusFetcher.data.success !== false) {
        pollStatus();
      } else {
        // If we get authentication errors, stop polling
        console.log("🔐 Authentication error detected, stopping polling");
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
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

    // Cleanup function
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [jobId, startAnalysis]); // Removed statusFetcher from dependencies

  // Handle status updates
  useEffect(() => {
    if (statusFetcher.state === "idle" && statusFetcher.data) {
      console.log("📊 Status update:", statusFetcher.data);
      console.log("🔍 Current UI state:", { state, hasStartedAnalysis, jobId });

      if (statusFetcher.data.success && statusFetcher.data.job) {
        const job = statusFetcher.data.job;
        console.log("📋 Job details:", {
          jobId: job.jobId,
          status: job.status,
          progress: job.progress,
          error: job.error,
          hasError: !!job.error,
        });

        setJobStatus(job);
        setProgress(job.progress || 0);

        if (job.status === "completed") {
          console.log("✅ Setting state to success");
          setState("success");
          setHasStartedAnalysis(false);
          setJobId(null); // Clear jobId to stop polling
          console.log("✅ Analysis completed successfully");
        } else if (job.status === "failed") {
          console.log("❌ Setting state to error for failed job");
          console.log("❌ Error details:", job.error);
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
          console.log("🔍 Error state set:", {
            state: "error",
            error: job.error,
          });
        } else if (job.status === "processing") {
          console.log("🔄 Analysis in progress:", job.progress + "%");
          // Stay on dashboard - don't change state
        } else if (job.status === "queued" || job.status === "pending") {
          console.log("⏳ Job is queued, waiting to start...");
          // Stay on dashboard - don't change state
        } else {
          console.log("📊 Job in other status:", job.status);
        }
      } else if (!statusFetcher.data.success) {
        // Handle authentication or other errors
        console.log("❌ Status check failed:", statusFetcher.data.error);
        console.log("🔍 Full error response:", statusFetcher.data);

        // Increment consecutive error counter
        consecutiveErrorsRef.current++;

        // Stop polling if we get too many consecutive errors
        if (consecutiveErrorsRef.current >= 5) {
          console.log("⚠️ Too many consecutive errors, stopping polling");
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          setState("error");
          setHasStartedAnalysis(false);
          setError({
            title: "Connection Error",
            description:
              "Unable to check analysis status due to repeated errors.",
            action: { content: "Try Again", onAction: startAnalysis },
            recommendations: [
              "Check your internet connection",
              "Try refreshing the page",
              "Contact support if the issue persists",
            ],
          });
          return;
        }

        // Check for authentication errors specifically
        const isAuthError =
          statusFetcher.data.error?.includes("Authentication") ||
          statusFetcher.data.error?.includes("authentication") ||
          statusFetcher.data.error?.includes("no shop in session") ||
          statusFetcher.data.error?.includes("Authentication failed") ||
          statusFetcher.data.status === 401 ||
          statusFetcher.data.status === 403 ||
          (statusFetcher.data.debug &&
            statusFetcher.data.debug.hasSession === false);

        if (isAuthError) {
          // Stop polling on authentication errors
          console.log("🔐 Authentication error detected, stopping polling");
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
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
        } else if (statusFetcher.data.status === 429) {
          // Handle rate limiting
          console.log("⏳ Rate limit error detected, pausing polling");
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          setState("error");
          setHasStartedAnalysis(false);
          setError({
            title: "Rate Limit Exceeded",
            description: "Too many requests. Please wait before trying again.",
            action: { content: "Try Again", onAction: startAnalysis },
            recommendations: [
              "Wait a few minutes before trying again",
              "The system is processing too many requests",
              "Contact support if the issue persists",
            ],
          });
        } else {
          // Handle other errors but don't stop polling immediately
          console.log("⚠️ Other error detected:", statusFetcher.data.error);
        }
      } else {
        // Reset consecutive error counter on success
        consecutiveErrorsRef.current = 0;
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

    // Clear any existing interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
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
