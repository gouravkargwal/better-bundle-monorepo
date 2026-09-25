/**
 * When the free period ends.
 *
 * Two conditions, both required. Revenue alone was the wrong gate: on a store
 * with a $1,500 average order a single attributed order clears a $1,000
 * threshold, so the merchant was asked to start paying on the strength of one
 * sale while the Proof page still read "Not enough data yet".
 *
 * The conditions block opposite failures, which is why this is an AND:
 *
 *   high average order:  1 order, $1,110  -> revenue met, orders not
 *   low average order:  30 orders, $300   -> orders met, revenue not
 *
 * The authority is the worker, which flips the subscription status —
 * see python-worker/app/domains/billing/repositories/billing_repository_v2.py.
 * This mirror exists so the admin app can show progress without waiting for a
 * webhook, and MUST be kept in step with `MIN_TRIAL_ORDERS` there.
 */

/** Attributed orders a merchant must see before the trial can end. */
export const MIN_TRIAL_ORDERS = 30;

export interface TrialProgress {
  revenueEarned: number;
  revenueThreshold: number;
  ordersEarned: number;
  ordersThreshold: number;
}

/** Whether both conditions are met. */
export function isTrialComplete(p: TrialProgress): boolean {
  return (
    p.revenueEarned >= p.revenueThreshold && p.ordersEarned >= p.ordersThreshold
  );
}

/**
 * Which condition is furthest from being met — the one worth showing.
 *
 * Showing both bars at once makes the merchant do the work of figuring out
 * what is actually holding things up. Naming the binding constraint answers
 * the only question they have.
 */
export function bindingConstraint(p: TrialProgress): "revenue" | "orders" {
  const revenueShare = p.revenueThreshold
    ? p.revenueEarned / p.revenueThreshold
    : 1;
  const ordersShare = p.ordersThreshold
    ? p.ordersEarned / p.ordersThreshold
    : 1;
  return revenueShare <= ordersShare ? "revenue" : "orders";
}
