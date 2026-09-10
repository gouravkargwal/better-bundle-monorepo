/**
 * The product promise, as a test.
 *
 * A currency amount may appear if and only if the result is statistically
 * significant. Everything else gets a sentence.
 *
 * This exists because the code it replaces did the opposite: it rendered
 * `SUM(offer_impressions.revenue_added)` — attributed revenue — under the label
 * "Incremental Revenue, measured against the control group", with a confidence
 * interval of `revenue * 0.9` to `revenue * 1.1` and a p-value of literal 0.01.
 * A merchant reading that page was told their money had been causally proven
 * when nothing had been measured at all. That must not be able to come back
 * through a refactor, so it is asserted rather than reviewed.
 */

import { describe, expect, it } from "vitest";

import {
  showsCurrency,
  type ProofResult,
} from "../../../features/impact/types/proof.types";
import { formatCurrency } from "../../../utils/currency";
import { SURFACES, isMeasurable } from "../../../lib/surfaces";

const ARM = {
  shoppers: 1000,
  converters: 120,
  conversionRate: 0.12,
  revenuePerShopper: 5.4,
  totalRevenue: 5400,
  aov: 45,
};

const RESULTS: ProofResult[] = [
  { state: "unavailable" },
  { state: "holdout_disabled" },
  { state: "not_measurable" },
  {
    state: "insufficient_data",
    controlConverters: 42,
    minControlOrders: 100,
    treatmentShoppers: 9000,
    controlShoppers: 1000,
  },
  {
    state: "not_significant",
    conversionLiftRel: 0.02,
    pValue: 0.31,
    treatment: ARM,
    control: ARM,
  },
  {
    state: "significant",
    incrementalRevenue: 3120,
    incrementalRevenueLower: 1840,
    incrementalRevenueUpper: 4400,
    conversionLiftRel: 0.156,
    conversionLiftRelLower: 0.06,
    conversionLiftRelUpper: 0.25,
    pValue: 0.023,
    treatment: ARM,
    control: ARM,
  },
];

describe("the currency rule", () => {
  it("shows money for significant results only", () => {
    for (const result of RESULTS) {
      expect(showsCurrency(result)).toBe(result.state === "significant");
    }
  });

  it("gives no revenue field to any unpowered state", () => {
    // The type system already forbids this; the assertion catches someone
    // widening the union back into the old non-nullable shape.
    for (const result of RESULTS) {
      if (result.state === "significant") continue;
      expect(result).not.toHaveProperty("incrementalRevenue");
      expect(result).not.toHaveProperty("incrementalRevenueLower");
      expect(result).not.toHaveProperty("incrementalRevenueUpper");
    }
  });

  it("gives no p-value to a state that has not been measured", () => {
    for (const result of RESULTS) {
      if (result.state === "significant" || result.state === "not_significant") {
        expect(typeof (result as { pValue: number }).pValue).toBe("number");
      } else {
        expect(result).not.toHaveProperty("pValue");
      }
    }
  });

  it("never reports AOV lift as a causal effect", () => {
    // AOV is conditional on converting, so the arms' converter populations
    // differ. That is selection on the outcome — no sample size fixes it.
    for (const result of RESULTS) {
      expect(result).not.toHaveProperty("aovLiftPercent");
    }
  });
});

describe("surface measurability is configuration, not observation", () => {
  it("marks checkout and thank-you as never measurable", () => {
    // Held at 0% holdout in holdout_service.SURFACE_HOLDOUT_PERCENT, so no
    // control group exists there and none ever will at that setting.
    expect(isMeasurable("mercury")).toBe(false);
    expect(isMeasurable("thank_you")).toBe(false);
  });

  it("keeps the holdout-eligible surfaces measurable", () => {
    expect(isMeasurable("phoenix")).toBe(true);
    expect(isMeasurable("apollo")).toBe(true);
    expect(isMeasurable("venus")).toBe(true);
  });

  it("covers all five surfaces so none can be silently omitted", () => {
    // The impact service used to carry a two-entry map, which is why phoenix,
    // thank_you and venus never appeared in any funnel.
    expect(Object.keys(SURFACES).sort()).toEqual(
      ["apollo", "mercury", "phoenix", "thank_you", "venus"].sort(),
    );
  });

  it("never shows an internal codename to a merchant", () => {
    for (const surface of Object.values(SURFACES)) {
      expect(surface.label.toLowerCase()).not.toContain(surface.key);
    }
  });
});

describe("money formatting", () => {
  it("labels non-USD amounts instead of printing a bare number", () => {
    // The replaced pattern was `currency === "USD" ? "$" : ""`, so every
    // non-USD merchant saw an unlabelled figure.
    const eur = formatCurrency(1234.5, "EUR");
    expect(eur).not.toBe("1,234.50");
    expect(eur).toMatch(/[€]|EUR/);
  });

  it("omits decimals for currencies that have no minor unit", () => {
    expect(formatCurrency(1234, "JPY")).not.toContain(".00");
    expect(formatCurrency(1234.5, "USD")).toContain(".50");
  });

  it("falls back to USD rather than throwing on a blank code", () => {
    expect(() => formatCurrency(10, "")).not.toThrow();
  });
});
