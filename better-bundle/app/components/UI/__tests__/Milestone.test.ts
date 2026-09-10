/**
 * Which moment gets marked, and — more importantly — when nothing does.
 *
 * A milestone card that fires on an ordinary day is noise on the page a
 * merchant checks daily, so "returns null" is the most common correct answer
 * and gets the most tests.
 */

import { describe, expect, it } from "vitest";

import { pickMilestone } from "../Milestone";
import type { ProofResult } from "../../../features/impact/types/proof.types";

const COLLECTING: ProofResult = {
  state: "insufficient_data",
  controlConverters: 0,
  minControlOrders: 100,
  treatmentShoppers: 10,
  controlShoppers: 17,
};

const PROVEN: ProofResult = {
  state: "significant",
  incrementalRevenue: 3120,
  incrementalRevenueLower: 1840,
  incrementalRevenueUpper: 4400,
  conversionLiftRel: 0.156,
  conversionLiftRelLower: 0.06,
  conversionLiftRelUpper: 0.25,
  pValue: 0.023,
  treatment: {
    shoppers: 1000, converters: 120, conversionRate: 0.12,
    revenuePerShopper: 5.4, totalRevenue: 5400, aov: 45,
  },
  control: {
    shoppers: 1000, converters: 100, conversionRate: 0.1,
    revenuePerShopper: 4.5, totalRevenue: 4500, aov: 45,
  },
};

function base(over: Partial<Parameters<typeof pickMilestone>[0]> = {}) {
  return {
    attributedRevenue: 0,
    trialRevenueEarned: 0,
    trialThreshold: 1000,
    isTrial: true,
    ordersInfluenced: 0,
    proof: COLLECTING,
    ...over,
  };
}

describe("nothing to celebrate", () => {
  it("is silent on a brand new shop", () => {
    expect(pickMilestone(base())).toBeNull();
  });

  it("is silent on an ordinary day mid-trial", () => {
    expect(
      pickMilestone(
        base({ attributedRevenue: 160, trialRevenueEarned: 160, ordersInfluenced: 4 }),
      ),
    ).toBeNull();
  });

  it("does not re-celebrate the first sale on the second one", () => {
    expect(
      pickMilestone(base({ attributedRevenue: 200, ordersInfluenced: 2 })),
    ).toBeNull();
  });
});

describe("the moments", () => {
  it("marks the very first attributed sale", () => {
    expect(
      pickMilestone(base({ attributedRevenue: 62.81, ordersInfluenced: 1 })),
    ).toBe("first_revenue");
  });

  it("warns before the free allowance runs out", () => {
    expect(pickMilestone(base({ trialRevenueEarned: 850 }))).toBe(
      "trial_nearly_done",
    );
  });

  it("marks the trial being complete", () => {
    expect(pickMilestone(base({ trialRevenueEarned: 1000 }))).toBe(
      "trial_complete",
    );
  });

  it("marks proven lift", () => {
    expect(pickMilestone(base({ proof: PROVEN, isTrial: false }))).toBe(
      "lift_proven",
    );
  });
});

describe("precedence", () => {
  it("puts proven lift above every billing milestone", () => {
    // The strongest thing this product can tell a merchant wins.
    expect(
      pickMilestone(
        base({ proof: PROVEN, trialRevenueEarned: 1000, ordersInfluenced: 1, attributedRevenue: 50 }),
      ),
    ).toBe("lift_proven");
  });

  it("puts a completed trial above a first sale", () => {
    expect(
      pickMilestone(
        base({ trialRevenueEarned: 1200, ordersInfluenced: 1, attributedRevenue: 1200 }),
      ),
    ).toBe("trial_complete");
  });

  it("ignores trial milestones once the shop is paying", () => {
    expect(
      pickMilestone(base({ isTrial: false, trialRevenueEarned: 1000 })),
    ).toBeNull();
  });

  it("does not divide by a zero threshold", () => {
    expect(() =>
      pickMilestone(base({ trialThreshold: 0, trialRevenueEarned: 10 })),
    ).not.toThrow();
  });
});
