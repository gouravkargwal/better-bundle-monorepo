/**
 * Dunning State Machine Service
 *
 * Manages the payment recovery (dunning) process for failed payments.
 * The state machine progresses through notification stages based on
 * days elapsed since the first payment failure.
 *
 * State machine:
 *   PAYMENT_FAILED → (Day 0) → NOTIFIED_1 → (Day 3) → NOTIFIED_2
 *   → (Day 7) → FINAL_WARNING → (Day 10) → SUSPENDED
 */

export enum DunningState {
  NOTIFIED_1 = "NOTIFIED_1",
  NOTIFIED_2 = "NOTIFIED_2",
  FINAL_WARNING = "FINAL_WARNING",
  SUSPENDED = "SUSPENDED",
}

export interface DunningInfo {
  state: DunningState | null;
  startedAt: Date | null;
  failureCount: number;
}

/**
 * Dunning schedule defining how many days after the first failure
 * each notification state becomes active.
 */
const DUNNING_SCHEDULE: { state: DunningState; afterDays: number }[] = [
  { state: DunningState.NOTIFIED_1, afterDays: 0 }, // Immediate
  { state: DunningState.NOTIFIED_2, afterDays: 3 }, // 3 days after 1st
  { state: DunningState.FINAL_WARNING, afterDays: 7 }, // 7 days after 1st
  { state: DunningState.SUSPENDED, afterDays: 10 }, // 10 days = suspension
];

/**
 * Determines the current dunning state based on failure count and
 * how many days have elapsed since the dunning period started.
 *
 * @param failureCount - Number of payment failures recorded
 * @param startedAt - Timestamp when the dunning period began (first failure)
 * @returns The current dunning state and whether suspension should be triggered
 */
export function getCurrentDunningState(
  failureCount: number,
  startedAt: Date | null,
): { state: DunningState | null; shouldSuspend: boolean } {
  if (!startedAt || failureCount === 0) {
    return { state: null, shouldSuspend: false };
  }

  const daysElapsed = Math.floor(
    (Date.now() - startedAt.getTime()) / (1000 * 60 * 60 * 24),
  );

  // Find the highest state that should be active based on days elapsed
  let currentState: DunningState | null = null;
  let shouldSuspend = false;

  for (const step of DUNNING_SCHEDULE) {
    if (daysElapsed >= step.afterDays) {
      if (step.state === DunningState.SUSPENDED) {
        shouldSuspend = true;
      } else {
        currentState = step.state;
      }
    }
  }

  return { state: currentState, shouldSuspend };
}

/**
 * Process a new payment failure and compute the resulting dunning state.
 *
 * @param existingDunning - The current dunning info before this failure
 * @returns The new state, whether suspension should trigger, and days since dunning started
 */
export function processPaymentFailure(existingDunning: DunningInfo): {
  newState: DunningState;
  shouldSuspend: boolean;
  daysSinceStart: number;
} {
  const now = new Date();
  const startedAt = existingDunning.startedAt || now;
  const failureCount = existingDunning.failureCount + 1;

  const daysSinceStart = startedAt
    ? Math.floor((now.getTime() - startedAt.getTime()) / (1000 * 60 * 60 * 24))
    : 0;

  const { state, shouldSuspend } = getCurrentDunningState(
    failureCount,
    startedAt,
  );

  return {
    newState: state || DunningState.NOTIFIED_1,
    shouldSuspend,
    daysSinceStart,
  };
}

/**
 * Process a successful payment, which resets the dunning process.
 *
 * @returns An indicator that dunning state should be reset
 */
export function processSuccessfulPayment(): { reset: true } {
  return { reset: true };
}
