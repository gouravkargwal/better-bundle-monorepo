/**
 * Venus attribution.
 *
 * Venus lives in the customer account area — order status, order index,
 * profile. It has no cart, so unlike Phoenix it can never stamp an impression
 * onto a cart line. The only thing it can observe is the click.
 *
 * So every Venus conversion is attributed by the click-then-bought path: the
 * click is reported against the impression, and the backend later checks
 * whether that exact recommended product appears in a paid order inside the
 * attribution window.
 *
 * That path over-credits by design — some of those customers were going to buy
 * the product regardless. The held-out control group is what turns the upper
 * bound into a billable number, which is why Venus impressions are bucketed
 * like every other surface.
 *
 * Replaces `api/analytics.ts`, which bootstrapped a session, linked client ids
 * and posted every view and click to `/api/interaction/track`. All three
 * endpoints were removed with the behaviour-tracking pipeline.
 */

import { BACKEND_URL } from "../config/constants";
import { logger } from "../utils/logger";
import { makeAuthenticatedRequest } from "../utils/jwt";

export type Outcome = "clicked" | "accepted" | "declined" | "ignored";

// Outcomes already sent, so a double-press cannot report twice.
const reported = new Set<string>();

/**
 * Report a terminal outcome for an impression.
 *
 * Never throws: attribution must not break the shopper's navigation. A lost
 * report costs the credit for one order, and the caller has nothing useful to
 * do about it.
 */
export async function reportOutcome(
  storage: any,
  impressionId: string | undefined,
  outcome: Outcome,
  revenueAdded?: number,
): Promise<boolean> {
  if (!impressionId) {
    logger.warn({ outcome }, "Venus: outcome reported with no impression_id");
    return false;
  }

  const key = `${impressionId}:${outcome}`;
  if (reported.has(key)) return false;
  reported.add(key);

  const body: Record<string, unknown> = {
    impression_id: impressionId,
    outcome,
  };
  if (revenueAdded != null && revenueAdded > 0) {
    body.revenue_added = revenueAdded;
  }

  try {
    const response = await makeAuthenticatedRequest(
      storage,
      `${BACKEND_URL}/api/interaction/outcome`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        keepalive: true,
      },
    );

    if (!response.ok) {
      throw new Error(`outcome API returned ${response.status}`);
    }
    return true;
  } catch (error) {
    reported.delete(key);
    logger.warn(
      {
        impressionId,
        outcome,
        error: error instanceof Error ? error.message : String(error),
      },
      "Venus: failed to report outcome",
    );
    return false;
  }
}

/** Customer clicked through to the recommended product's own page. */
export function reportClick(storage: any, impressionId: string | undefined) {
  return reportOutcome(storage, impressionId, "clicked");
}
