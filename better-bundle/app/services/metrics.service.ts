/**
 * Simple metrics counters for key billing operations.
 *
 * Emits structured `[Metric]` log lines that can be parsed by log-aggregation
 * tools (OpenObserve, Loki, etc.) to build dashboards and alerts.
 *
 * Usage:
 *   import { incrementCounter } from "~/services/metrics.service";
 *   incrementCounter("billing.setup.started", { shop, plan: planName });
 */

/**
 * Increment a named counter with optional key-value tags.
 *
 * The metric is emitted as a structured JSON line prefixed with `[Metric]`
 * so log shippers can extract and sum it.
 *
 * @param name   – Metric name, e.g. "billing.setup.started"
 * @param tags   – Optional key-value pairs for filtering/grouping
 */
export function incrementCounter(
  name: string,
  tags?: Record<string, string | number | undefined>,
): void {
  const cleanTags: Record<string, string | number> = {};
  if (tags) {
    for (const [k, v] of Object.entries(tags)) {
      if (v !== undefined) {
        cleanTags[k] = v;
      }
    }
  }

  // Flatten to single-line JSON so each line is one event
  const payload = JSON.stringify({
    metric: name,
    ...(Object.keys(cleanTags).length > 0 ? cleanTags : undefined),
  });
  console.log(`[Metric] ${payload}`);
}
