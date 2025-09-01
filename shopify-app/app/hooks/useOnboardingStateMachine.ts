import { useMachine } from "@xstate/react";
import { useEffect, useState } from "react";
import { onboardingMachine } from "../machines/onboardingMachine";

export const useOnboardingStateMachine = () => {
  const [isClient, setIsClient] = useState(false);
  const [state, send] = useMachine(onboardingMachine);

  // Ensure we're on the client side before accessing localStorage
  useEffect(() => {
    setIsClient(true);
  }, []);

  // Load state from localStorage on mount
  useEffect(() => {
    if (!isClient) return;

    try {
      const savedState = localStorage.getItem("onboarding-state");
      const savedContext = localStorage.getItem("onboarding-context");
      
      if (savedState && savedContext) {
        const parsedState = JSON.parse(savedState);
        const parsedContext = JSON.parse(savedContext);
        
        // Restore the context
        send({ type: "RESTORE", context: parsedContext });
      }
    } catch (error) {
      console.error("Failed to load onboarding state:", error);
    }
  }, [isClient, send]);

  // Save state to localStorage whenever it changes
  useEffect(() => {
    if (!isClient) return;

    try {
      localStorage.setItem("onboarding-state", JSON.stringify(state.value));
      localStorage.setItem("onboarding-context", JSON.stringify(state.context));
    } catch (error) {
      console.error("Failed to save onboarding state:", error);
    }
  }, [state, isClient]);

  const startAnalysis = (shopId: string) => {
    if (!isClient) return;
    send({ type: "START_ANALYSIS", shopId });
  };

  const markAnalysisComplete = () => {
    if (!isClient) return;
    send({ type: "ANALYSIS_COMPLETE" });
  };

  const markWidgetConfigured = () => {
    if (!isClient) return;
    send({ type: "WIDGET_CONFIGURED" });
  };

  const markDataCollected = () => {
    if (!isClient) return;
    send({ type: "DATA_COLLECTED" });
  };

  const reset = () => {
    if (!isClient) return;
    send({ type: "RESET" });
  };

  const isInState = (stateName: string) => {
    return state.matches(stateName);
  };

  const canTransitionTo = (stateName: string) => {
    return state.can({ type: "GO_TO_STEP", step: stateName });
  };

  return {
    state,
    context: state.context,
    send,
    startAnalysis,
    markAnalysisComplete,
    markWidgetConfigured,
    markDataCollected,
    reset,
    isInState,
    canTransitionTo,
    isClient,
  };
};
