import { createMachine, assign } from "xstate";

export interface OnboardingContext {
  shopId: string;
  analysisJobId?: string;
  widgetConfigured: boolean;
  hasBundleData: boolean;
  error?: string;
  progress: number;
}

export type OnboardingEvent =
  | { type: "START_ANALYSIS"; shopId: string }
  | { type: "ANALYSIS_COMPLETE" }
  | { type: "WIDGET_CONFIGURED" }
  | { type: "DATA_COLLECTED" }
  | { type: "RESET" };

export const onboardingMachine = createMachine({
  id: "onboarding",
  initial: "welcome",
  context: {
    shopId: "",
    analysisJobId: undefined,
    widgetConfigured: false,
    hasBundleData: false,
    error: undefined,
    progress: 0,
  },
  states: {
    welcome: {
      on: {
        START_ANALYSIS: {
          target: "analysis_running",
          actions: "setShopId",
        },
      },
    },
    analysis_running: {
      on: {
        ANALYSIS_COMPLETE: {
          target: "widget_setup",
        },
        WIDGET_CONFIGURED: {
          target: "widget_setup",
        },
      },
    },
    widget_setup: {
      on: {
        WIDGET_CONFIGURED: {
          target: "dashboard",
        },
      },
    },
    dashboard: {
      on: {
        DATA_COLLECTED: {
          target: "dashboard",
          actions: "setBundleData",
        },
        RESET: {
          target: "welcome",
          actions: "resetContext",
        },
      },
    },
  },
});
