import { Badge, BlockStack, Box, Button, InlineStack, Text } from "@shopify/polaris";

import type { ProofResult } from "../../features/impact/types/proof.types";
import { formatCurrency } from "../../utils/currency";

/**
 * The moments worth marking.
 *
 * This app has genuine emotional beats and used to acknowledge none of them —
 * the first sale a recommendation earned, the trial allowance running out, and
 * above all the first time lift became statistically real. That last one is the
 * entire promise of the product landing, and it happened by a badge quietly
 * changing colour.
 *
 * One card, shown at most once per page, chosen by precedence. Deliberately not
 * a toast or a confetti burst: this sits above a merchant's money, and a
 * dismissible novelty would read as noise on the page they check every day.
 * Built from Polaris `Box`, `Badge` and `Text` only — nothing custom-styled, so
 * it reads as part of the admin rather than as an advert inside it.
 */

export type MilestoneKind =
  | "first_revenue"
  | "trial_nearly_done"
  | "trial_complete"
  | "lift_proven";

interface MilestoneProps {
  attributedRevenue: number;
  trialRevenueEarned: number;
  trialThreshold: number;
  isTrial: boolean;
  ordersInfluenced: number;
  proof: ProofResult;
  currency: string;
}

/**
 * Which milestone to show, if any.
 *
 * Precedence runs strongest-signal first: a proven lift outranks a billing
 * threshold, which outranks a first sale. Exported so it can be tested without
 * rendering — the interesting logic is the choosing, not the markup.
 */
export function pickMilestone({
  attributedRevenue,
  trialRevenueEarned,
  trialThreshold,
  isTrial,
  ordersInfluenced,
  proof,
}: Omit<MilestoneProps, "currency">): MilestoneKind | null {
  // Proven incrementality is the strongest thing this product can ever tell a
  // merchant, so nothing outranks it.
  if (proof.state === "significant") return "lift_proven";

  if (isTrial && trialThreshold > 0) {
    const progress = trialRevenueEarned / trialThreshold;
    if (progress >= 1) return "trial_complete";
    // 80% is late enough to be worth a heads-up and early enough that the
    // first charge is not a surprise.
    if (progress >= 0.8) return "trial_nearly_done";
  }

  // Only for the very first one; after that it is just business as usual.
  if (ordersInfluenced === 1 && attributedRevenue > 0) return "first_revenue";

  return null;
}

export function Milestone(props: MilestoneProps) {
  const kind = pickMilestone(props);
  if (!kind) return null;

  const { currency, trialThreshold, trialRevenueEarned, proof } = props;
  const money = (n: number) => formatCurrency(n, currency);

  const content: Record<
    MilestoneKind,
    { badge: string; title: string; body: string; action?: { label: string; url: string } }
  > = {
    first_revenue: {
      badge: "First sale",
      title: "A recommendation just earned its first sale",
      body: `${money(props.attributedRevenue)} of this order came from a product we suggested. You're not billed for any of it yet — the first ${money(trialThreshold)} is free.`,
      action: { label: "See where it happened", url: "/app/impact" },
    },
    trial_nearly_done: {
      badge: "Heads up",
      title: `You've used most of your free allowance`,
      body: `Recommendations have earned you ${money(trialRevenueEarned)} of the ${money(trialThreshold)} that comes free. After that it's 3% of attributed revenue, capped monthly — no surprises.`,
      action: { label: "See what that means", url: "/app/billing" },
    },
    trial_complete: {
      badge: "Trial complete",
      title: `Recommendations have earned you ${money(trialRevenueEarned)}`,
      body: `That's past your free allowance, so billing starts from here — 3% of attributed revenue, never more than the monthly cap.`,
      action: { label: "Review your plan", url: "/app/billing" },
    },
    lift_proven: {
      badge: "Proven",
      title: "We can now prove recommendations are making you money",
      body:
        proof.state === "significant"
          ? `Shoppers who saw recommendations spent measurably more than the control group who didn't. ${money(proof.incrementalRevenue)} of your revenue wouldn't have happened otherwise.`
          : "",
      action: { label: "See the proof", url: "/app/impact" },
    },
  };

  const c = content[kind];

  return (
    <Box
      padding="400"
      borderRadius="300"
      background="bg-surface-secondary"
      borderInlineStartWidth="050"
      borderColor="border-brand"
    >
      <BlockStack gap="200">
        <InlineStack gap="200" blockAlign="center">
          <Badge tone="success">{c.badge}</Badge>
        </InlineStack>

        <Text as="h2" variant="headingMd">
          {c.title}
        </Text>
        <Text as="p" tone="subdued">
          {c.body}
        </Text>

        {c.action && (
          <InlineStack>
            <Button url={c.action.url} variant="plain">
              {c.action.label}
            </Button>
          </InlineStack>
        )}
      </BlockStack>
    </Box>
  );
}
