import { Badge, BlockStack, Button, InlineStack, Text } from "@shopify/polaris";
import type { ProofResult } from "../../features/impact/types/proof.types";
import { formatCurrency } from "../../utils/currency";

/**
 * The single place that turns a statistical result into words for a merchant.
 *
 * Three surfaces consume it — the Proof summary, each Proof per-placement row,
 * and the one-line status on Home. Having one component means those three can
 * never drift into telling the merchant different things about the same number,
 * which is exactly what happened when Overview and Impact each rendered their
 * own copy of "measured against a control group".
 *
 * The rule it enforces: a currency amount appears if and only if the state is
 * `significant`. Every other state gets a sentence explaining why there is no
 * number yet, and what would change that.
 */

interface ResultStateProps {
  result: ProofResult;
  currencyCode: string;
  /** Holdout percentage, for copy like "the 10% who didn't". */
  holdoutPercent?: number;
  /** Human window description, e.g. "the last 30 days". */
  window?: string;
  /** Compact rendering for a table cell or Home's one-liner. */
  compact?: boolean;
}

type Tone = "success" | "info" | "attention" | "warning" | undefined;

const BADGE: Record<ProofResult["state"], { tone: Tone; label: string }> = {
  significant: { tone: "success", label: "Measured lift" },
  not_significant: { tone: "attention", label: "No clear difference yet" },
  insufficient_data: { tone: "info", label: "Not enough data yet" },
  not_measurable: { tone: undefined, label: "Not measurable" },
  holdout_disabled: { tone: "warning", label: "Measurement off" },
  unavailable: { tone: undefined, label: "Unavailable" },
};

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function ResultState({
  result,
  currencyCode,
  holdoutPercent = 10,
  window = "the last 30 days",
  compact = false,
}: ResultStateProps) {
  const badge = BADGE[result.state];
  const money = (n: number) => formatCurrency(n, currencyCode);

  let headline: string | null = null;
  let body: string;
  let action: { label: string; url: string } | null = null;

  switch (result.state) {
    case "significant":
      headline = money(result.incrementalRevenue);
      body =
        `Shoppers who saw personalised recommendations spent ${pct(result.conversionLiftRel)} more ` +
        `than the ${holdoutPercent}% who saw generic ones. Over ${window} that's money you ` +
        `wouldn't otherwise have made. We're 95% confident the real figure sits ` +
        `between ${money(result.incrementalRevenueLower)} and ` +
        `${money(result.incrementalRevenueUpper)}.`;
      action = { label: "See what you were charged", url: "/app/billing" };
      break;

    case "not_significant":
      // A point estimate, as a percentage. Deliberately no currency: an
      // interval that straddles zero is not a revenue figure.
      body =
        `Shoppers who saw personalised recommendations spent about the same as those who ` +
        `saw generic ones. The ${pct(result.conversionLiftRel)} difference observed so far is ` +
        `within normal week-to-week variation, so we are not reporting it as a ` +
        `lift. Adding placements increases the volume needed to settle it.`;
      action = { label: "Add another placement", url: "/app/extensions" };
      break;

    case "insufficient_data":
      body =
        `Not enough data yet. To confirm recommendations caused a sale we ` +
        `compare against the shoppers who were shown generic recommendations, which needs about ` +
        `${result.minControlOrders} orders from that group. You have ` +
        `${result.controlConverters}. This does not affect your bill — ` +
        `attributed revenue is tracked and charged as normal.`;
      break;

    case "not_measurable":
      body =
        `This placement currently has no control group, so its incrementality cannot be measured. ` +
        `Your attributed revenue is tracked and billed as normal.`;
      break;

    case "holdout_disabled":
      body =
        `The ${holdoutPercent}% control group is switched off, so every shopper is ` +
        `seeing personalised recommendations and there's no baseline left to compare them to. ` +
        `Your billing carries on unaffected — but while it's off, we can't show ` +
        `you what personalised recommendations are actually adding.`;
      action = { label: "Turn the control group back on", url: "/app/settings" };
      break;

    case "unavailable":
      body =
        `We can't calculate lift right now. Your attributed revenue and billing are ` +
        `unaffected — this only affects the incrementality measurement.`;
      break;
  }

  if (compact) {
    return (
      <InlineStack gap="200" blockAlign="center" wrap={false}>
        <Badge tone={badge.tone}>{badge.label}</Badge>
        {headline && (
          <Text as="span" variant="headingMd" fontWeight="semibold">
            {headline}
          </Text>
        )}
      </InlineStack>
    );
  }

  return (
    <BlockStack gap="300">
      <InlineStack gap="200" blockAlign="center">
        <Badge tone={badge.tone}>{badge.label}</Badge>
      </InlineStack>

      {headline && (
        <Text as="p" variant="heading2xl" fontWeight="bold">
          {headline}
        </Text>
      )}

      <Text as="p" tone="subdued">
        {body}
      </Text>

      {action && (
        <InlineStack>
          <Button url={action.url} variant="plain">
            {action.label}
          </Button>
        </InlineStack>
      )}
    </BlockStack>
  );
}
