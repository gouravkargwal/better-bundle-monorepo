/**
 * The result of asking "did recommendations actually add revenue?"
 *
 * Modelled as a discriminated union on purpose. The type it replaces had
 * non-nullable `pValue`, `incrementalRevenueLower` and `incrementalRevenueUpper`
 * fields, so every code path had to put *something* in them — which is how the
 * app ended up shipping `pValue: isSignificant ? 0.01 : 0.5` and a confidence
 * interval of `revenue * 0.9` to `revenue * 1.1`.
 *
 * With a union, the statistics only exist on the one variant that has them.
 * A component cannot render a p-value it does not have, because it will not
 * compile. The honesty is enforced by the type checker rather than by review.
 */

export type ProofState =
  /** Could not reach the statistics service. Say so; do not imply zero. */
  | "unavailable"
  /** The merchant switched the control group off. Nothing to compare against. */
  | "holdout_disabled"
  /** This surface shows an offer to everyone by design — no control group exists. */
  | "not_measurable"
  /** Real holdout, not yet enough control orders to be reliable. */
  | "insufficient_data"
  /** Powered, but the difference is not distinguishable from zero. */
  | "not_significant"
  /** Powered, and the difference is real. The ONLY state that shows money. */
  | "significant";

export interface ArmStats {
  shoppers: number;
  converters: number;
  conversionRate: number;
  revenuePerShopper: number;
  totalRevenue: number;
  /** Descriptive only. Never given a p-value — see the note in ProofResult. */
  aov: number;
}

export type ProofResult =
  | { state: "unavailable" }
  | { state: "holdout_disabled" }
  | { state: "not_measurable" }
  | {
      state: "insufficient_data";
      controlConverters: number;
      minControlOrders: number;
      treatmentShoppers: number;
      controlShoppers: number;
    }
  | {
      state: "not_significant";
      /** Point estimate only. Shown as a percentage, never as currency. */
      conversionLiftRel: number;
      pValue: number;
      treatment: ArmStats;
      control: ArmStats;
    }
  | {
      state: "significant";
      incrementalRevenue: number;
      incrementalRevenueLower: number;
      incrementalRevenueUpper: number;
      conversionLiftRel: number;
      conversionLiftRelLower: number;
      conversionLiftRelUpper: number;
      pValue: number;
      treatment: ArmStats;
      control: ArmStats;
    };

/**
 * Only `significant` carries currency fields. This is the product promise in
 * one line, and it is why the union exists.
 *
 * Note that `not_significant` deliberately has no `incrementalRevenue`: a point
 * estimate whose interval straddles zero is not a revenue figure, and showing
 * it next to a currency symbol invites the merchant to read it as one.
 *
 * AOV lift is intentionally absent from every variant. AOV is conditional on
 * converting, so the two arms' converter populations differ — that is selection
 * on the outcome, and the difference is not a causal effect no matter how many
 * orders you gather. Per-arm AOV is reported inside `ArmStats` as description.
 */
export function showsCurrency(result: ProofResult): boolean {
  return result.state === "significant";
}

export interface SurfaceProofRow {
  surface: string;
  label: string;
  result: ProofResult;
}
