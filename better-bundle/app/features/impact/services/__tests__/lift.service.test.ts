/**
 * The boundary where nullable API fields become a shape the UI cannot misuse.
 *
 * The important case is the last one: if the worker ever says "significant"
 * without the numbers to back it, we must NOT render a headline with a blank or
 * zero in it. A missing statistic is a bug on our side, not a result to show a
 * merchant.
 */

import { describe, expect, it } from "vitest";

import { toProofResult } from "../lift.service";
import { showsCurrency } from "../../types/proof.types";

const ARM = {
  shoppers: 10000,
  converters: 500,
  conversion_rate: 0.05,
  revenue_per_shopper: 2.5,
  total_revenue: 25000,
  aov: 50,
};

function response(overrides: Record<string, unknown> = {}) {
  return {
    state: "insufficient_data",
    treatment: ARM,
    control: { ...ARM, converters: 42 },
    min_control_orders: 100,
    surfaces_measurable: ["phoenix", "apollo", "venus"],
    surfaces_not_measurable: ["mercury", "thank_you"],
    currency_code: "USD",
    conversion_lift_rel: null,
    conversion_lift_rel_lower: null,
    conversion_lift_rel_upper: null,
    p_value: null,
    incremental_revenue: null,
    incremental_revenue_lower: null,
    incremental_revenue_upper: null,
    ...overrides,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any;
}

describe("toProofResult", () => {
  it("carries the control-order progress on insufficient_data", () => {
    const r = toProofResult(response());

    expect(r.state).toBe("insufficient_data");
    if (r.state !== "insufficient_data") throw new Error("narrowing");
    expect(r.controlConverters).toBe(42);
    expect(r.minControlOrders).toBe(100);
    expect(showsCurrency(r)).toBe(false);
  });

  it("maps holdout_disabled and not_measurable to bare states", () => {
    expect(toProofResult(response({ state: "holdout_disabled" })).state).toBe(
      "holdout_disabled",
    );
    expect(toProofResult(response({ state: "not_measurable" })).state).toBe(
      "not_measurable",
    );
  });

  it("keeps a not_significant point estimate but no money", () => {
    const r = toProofResult(
      response({ state: "not_significant", conversion_lift_rel: 0.02, p_value: 0.31 }),
    );

    expect(r.state).toBe("not_significant");
    if (r.state !== "not_significant") throw new Error("narrowing");
    expect(r.conversionLiftRel).toBeCloseTo(0.02);
    expect(showsCurrency(r)).toBe(false);
    expect(r).not.toHaveProperty("incrementalRevenue");
  });

  it("passes a fully-populated significant result through", () => {
    const r = toProofResult(
      response({
        state: "significant",
        conversion_lift_rel: 0.156,
        conversion_lift_rel_lower: 0.06,
        conversion_lift_rel_upper: 0.25,
        p_value: 0.023,
        incremental_revenue: 3120,
        incremental_revenue_lower: 1840,
        incremental_revenue_upper: 4400,
      }),
    );

    expect(r.state).toBe("significant");
    if (r.state !== "significant") throw new Error("narrowing");
    expect(r.incrementalRevenue).toBe(3120);
    expect(r.incrementalRevenueLower).toBe(1840);
    expect(showsCurrency(r)).toBe(true);
  });

  it("downgrades a significant claim that is missing its numbers", () => {
    // Never render a currency headline built from nulls.
    const r = toProofResult(
      response({
        state: "significant",
        conversion_lift_rel: 0.156,
        p_value: 0.023,
        incremental_revenue: null,
      }),
    );

    expect(r.state).toBe("not_significant");
    expect(showsCurrency(r)).toBe(false);
  });

  it("treats an unknown state as unavailable rather than guessing", () => {
    expect(toProofResult(response({ state: "banana" })).state).toBe("unavailable");
  });
});
