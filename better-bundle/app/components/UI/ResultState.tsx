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
        `Shoppers who saw recommendations spent ${pct(result.conversionLiftRel)} more than ` +
        `the ${holdoutPercent}% who didn't. Over ${window} that's revenue you wouldn't ` +
        `otherwise have had. We're 95% confident the true figure is between ` +
        `${money(result.incrementalRevenueLower)} and ${money(result.incrementalRevenueUpper)}.`;
      action = { label: "See what you were charged", url: "/app/billing" };
      break;

    case "not_significant":
      // A point estimate, as a percentage. Deliberately no currency: an
      // interval that straddles zero is not a revenue figure.
      body =
        `Shoppers who saw recommendations spent about the same as the control group. ` +
        `The difference so far (${pct(result.conversionLiftRel)}) is small enough that it ` +
        `could be normal week-to-week variation, so we won't claim it as a lift.`;
      action = { label: "Add another placement", url: "/app/extensions" };
      break;

    case "insufficient_data":
      body =
        `We can't tell yet. Measuring lift reliably needs about ` +
        `${result.minControlOrders} orders from the control group — you have ` +
        `${result.controlConverters}. This doesn't affect your billing: attributed ` +
        `revenue is tracked and charged as usual, and you can see it on Home.`;
      break;

    case "not_measurable":
      body =
        `Checkout and thank-you page recommendations are shown to every shopper by ` +
        `design, so there's no control group there to compare against. To measure ` +
        `lift, use a placement that supports one: product pages, post-purchase, or ` +
        `customer account.`;
      action = { label: "Add a measurable placement", url: "/app/extensions" };
      break;

    case "holdout_disabled":
      body =
        `There's nothing to compare against. The ${holdoutPercent}% control group is ` +
        `switched off, so every shopper sees recommendations and we have no baseline ` +
        `for what they'd have spent without them. Your billing is unaffected — but ` +
        `until it's back on, we can't prove any of it was incremental.`;
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
