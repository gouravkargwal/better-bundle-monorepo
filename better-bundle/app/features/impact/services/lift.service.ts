import { ALL_SURFACES, type SurfaceKey } from "../../../lib/surfaces";
import type {
  ArmStats,
  ProofResult,
  SurfaceProofRow,
} from "../types/proof.types";

/**
 * Proxy to the incrementality engine in python-worker.
 *
 * Statistics live there because `math.erf` is Python stdlib (TypeScript has no
 * erf), because the pure functions get real known-answer tests under pytest,
 * and — most importantly — because `MIN_CONTROL_ORDERS`, `P_VALUE_THRESHOLD`
 * and `SURFACE_HOLDOUT_PERCENT` live in `holdout_service.py`. The engine has to
 * read the same constants that produced the arm assignment; duplicating `100`
 * and `0.05` into TypeScript guarantees they drift apart.
 *
 * Follows `getEdgeStatus` exactly: 4s timeout, degrade to a state rather than
 * throw. Lift is worth knowing but must never take the dashboard down, so an
 * unreachable worker yields `{ state: "unavailable" }` and the page still
 * renders every deterministic number from Postgres.
 */

const TIMEOUT_MS = 4_000;

interface LiftApiArm {
  shoppers: number;
  converters: number;
  conversion_rate: number;
  revenue_per_shopper: number;
  total_revenue: number;
  aov: number;
}

interface LiftApiResponse {
  state: string;
  treatment: LiftApiArm;
  control: LiftApiArm;
  min_control_orders: number;
  surfaces_measurable: string[];
  surfaces_not_measurable: string[];
  currency_code: string;
  conversion_lift_rel: number | null;
  conversion_lift_rel_lower: number | null;
  conversion_lift_rel_upper: number | null;
  p_value: number | null;
  incremental_revenue: number | null;
  incremental_revenue_lower: number | null;
  incremental_revenue_upper: number | null;
}

function arm(a: LiftApiArm): ArmStats {
  return {
    shoppers: a.shoppers,
    converters: a.converters,
    conversionRate: a.conversion_rate,
    revenuePerShopper: a.revenue_per_shopper,
    totalRevenue: a.total_revenue,
    aov: a.aov,
  };
}

/**
 * Map the wire response onto the discriminated union.
 *
 * This function is the boundary where nullable API fields become a shape the
 * UI cannot misuse. If the worker ever claims `significant` without the numbers
 * to back it, we downgrade to `not_significant` rather than render a blank
 * headline — a missing statistic is a bug on our side, not a result to show a
 * merchant.
 */
export function toProofResult(data: LiftApiResponse): ProofResult {
  const treatment = arm(data.treatment);
  const control = arm(data.control);

  switch (data.state) {
    case "holdout_disabled":
      return { state: "holdout_disabled" };

    case "not_measurable":
      return { state: "not_measurable" };

    case "insufficient_data":
      return {
        state: "insufficient_data",
        controlConverters: control.converters,
        minControlOrders: data.min_control_orders,
        treatmentShoppers: treatment.shoppers,
        controlShoppers: control.shoppers,
      };

    case "significant": {
      const hasAll =
        data.incremental_revenue !== null &&
        data.incremental_revenue_lower !== null &&
        data.incremental_revenue_upper !== null &&
        data.conversion_lift_rel !== null &&
        data.conversion_lift_rel_lower !== null &&
        data.conversion_lift_rel_upper !== null &&
        data.p_value !== null;

      if (!hasAll) {
        return {
          state: "not_significant",
          conversionLiftRel: data.conversion_lift_rel ?? 0,
          pValue: data.p_value ?? 1,
          treatment,
          control,
        };
      }

      return {
        state: "significant",
        incrementalRevenue: data.incremental_revenue!,
        incrementalRevenueLower: data.incremental_revenue_lower!,
        incrementalRevenueUpper: data.incremental_revenue_upper!,
        conversionLiftRel: data.conversion_lift_rel!,
        conversionLiftRelLower: data.conversion_lift_rel_lower!,
        conversionLiftRelUpper: data.conversion_lift_rel_upper!,
        pValue: data.p_value!,
        treatment,
        control,
      };
    }

    case "not_significant":
      return {
        state: "not_significant",
        conversionLiftRel: data.conversion_lift_rel ?? 0,
        pValue: data.p_value ?? 1,
        treatment,
        control,
      };

    default:
      // An unrecognised state must not be guessed at.
      return { state: "unavailable" };
  }
}

async function fetchLift(
  shopId: string,
  surface?: SurfaceKey,
): Promise<ProofResult> {
  const backendUrl = process.env.PYTHON_WORKER_API_URL;
  if (!backendUrl) return { state: "unavailable" };

  const query = surface ? `?surface=${encodeURIComponent(surface)}` : "";

  try {
    const response = await fetch(
      `${backendUrl}/api/v1/impact/lift/${shopId}${query}`,
      { signal: AbortSignal.timeout(TIMEOUT_MS) },
    );
    if (!response.ok) return { state: "unavailable" };
    return toProofResult((await response.json()) as LiftApiResponse);
  } catch {
    return { state: "unavailable" };
  }
}

/** Store-level result, across every holdout-eligible surface. */
export async function getLiftSummary(shopId: string): Promise<ProofResult> {
  return fetchLift(shopId);
}

/**
 * One row per surface, always all five.
 *
 * Surfaces that cannot be measured are answered locally from the registry
 * rather than by asking the worker — the answer is configuration, so there is
 * no reason to spend a request discovering it, and it keeps the row count fixed
 * even if the worker is unreachable. The two-entry map this replaces is why
 * phoenix, thank_you and venus never appeared in any funnel.
 */
export async function getLiftBySurface(
  shopId: string,
): Promise<SurfaceProofRow[]> {
  const results = await Promise.all(
    ALL_SURFACES.map(async (surface) => {
      if (!surface.measurable) {
        return {
          surface: surface.key,
          label: surface.label,
          result: { state: "not_measurable" } as ProofResult,
        };
      }
      return {
        surface: surface.key,
        label: surface.label,
        result: await fetchLift(shopId, surface.key),
      };
    }),
  );
  return results;
}
