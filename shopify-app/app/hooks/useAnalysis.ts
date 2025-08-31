import { useState, useCallback, useEffect } from "react";
import { useFetcher } from "@remix-run/react";
import type { AnalysisState, ErrorState } from "../types";
import { PROGRESS_CONFIG } from "../constants";

export function useAnalysis() {
  const [state, setState] = useState<AnalysisState>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<ErrorState | null>(null);
  const [hasStartedAnalysis, setHasStartedAnalysis] = useState(false);

  const analysisFetcher = useFetcher<any>();

  // Start analysis with validation
  const startAnalysis = useCallback(() => {
    if (hasStartedAnalysis) return; // Prevent multiple submissions

    setState("loading");
    setProgress(0);
    setError(null);
    setHasStartedAnalysis(true);

    // Go straight to analysis - it will handle data collection if needed
    analysisFetcher.submit(
      {},
      { method: "POST", action: "/api/analysis/start" },
    );
  }, [analysisFetcher, hasStartedAnalysis]);

  // Handle analysis response
  useEffect(() => {
    if (analysisFetcher.state === "idle" && analysisFetcher.data) {
      setHasStartedAnalysis(false); // Reset flag

      if (analysisFetcher.data.success) {
        setState("success");
      } else {
        setState("error");
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

  // Progress simulation
  useEffect(() => {
    if (state === "loading") {
      const interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= PROGRESS_CONFIG.MAX_PROGRESS) return prev;
          return (
            prev +
            Math.random() * PROGRESS_CONFIG.MAX_INCREMENT +
            PROGRESS_CONFIG.MIN_INCREMENT
          );
        });
      }, PROGRESS_CONFIG.UPDATE_INTERVAL);
      return () => clearInterval(interval);
    }
  }, [state]);

  const handleRetry = useCallback(() => {
    setState("idle");
    setError(null);
    setHasStartedAnalysis(false);
  }, []);

  return {
    state,
    progress,
    error,
    startAnalysis,
    handleRetry,
    isLoading: analysisFetcher.state !== "idle",
  };
}
