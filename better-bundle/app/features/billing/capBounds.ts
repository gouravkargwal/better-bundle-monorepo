/**
 * Bounds for the merchant-chosen spend cap.
 *
 * Defined once and imported by both the UI and the two server routes that
 * accept a cap. The server is the one that enforces them — the client picking
 * a value is a convenience, not a permission — but they have to agree, or the
 * slider offers amounts the API then rejects.
 */

/** Below this, a real store buys a suspension within days. */
export const MIN_CAP = 5;

/** Fat-finger guard. The cap is a ceiling, not a charge — it can be raised. */
export const MAX_CAP = 10000;

export const CAP_STEP = 5;

/** Clamp and round an untrusted amount to a value we will accept. */
export function clampCap(amount: number): number {
  const rounded = Math.round(amount * 100) / 100;
  return Math.min(MAX_CAP, Math.max(MIN_CAP, rounded));
}

export function isCapInRange(amount: number): boolean {
  return Number.isFinite(amount) && amount >= MIN_CAP && amount <= MAX_CAP;
}
