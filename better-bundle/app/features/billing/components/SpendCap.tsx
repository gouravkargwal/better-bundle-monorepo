import { useState } from "react";
import {
  Banner,
  BlockStack,
  Button,
  Card,
  InlineStack,
  ProgressBar,
  Text,
} from "@shopify/polaris";
import { MAX_CAP, MIN_CAP } from "../capBounds";
import { CapSlider } from "./CapSlider";

interface SpendCapProps {
  /** Commission charged so far in the current 30-day cycle. */
  usageThisCycle: number;
  /** The ceiling the merchant approved for this cycle. */
  cappedAmount: number;
  /** Share of attributed revenue charged, e.g. 0.03. */
  commissionRate: number;
  shopCurrency: string;
}

// Ask before the cap is reached, not after. Hitting it suspends
// recommendations, which costs the merchant sales — so the same message that
// reads as a failure notice at 100% reads as a growth conversation at 80%.
const WARN_AT = 0.8;

export function SpendCap({
  usageThisCycle,
  cappedAmount,
  commissionRate,
  shopCurrency,
}: SpendCapProps) {
  const [draftCap, setDraftCap] = useState(
    Math.min(MAX_CAP, Math.max(MIN_CAP, Math.round(cappedAmount * 2))),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: shopCurrency,
      maximumFractionDigits: 0,
    }).format(amount);

  const used = cappedAmount > 0 ? usageThisCycle / cappedAmount : 0;
  const nearLimit = used >= WARN_AT;

  // Merchants do not think in commission ceilings, they think in sales. At 3%,
  // a $50 cap is really "about $1,600 of recommended sales a month" — which is
  // the number they are actually deciding about.
  const salesCovered = (cap: number) =>
    commissionRate > 0 ? cap / commissionRate : 0;

  const requestNewCap = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch("/api/billing/cap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cappedAmount: draftCap }),
      });
      const result = await response.json();

      if (result.success && result.confirmationUrl) {
        // Shopify requires the merchant to approve a cap change; nothing takes
        // effect until they do, so hand off to their approval screen.
        window.top!.location.href = result.confirmationUrl;
        return;
      }
      setError(result.error || "Could not start the cap update.");
    } catch {
      setError("Could not reach Shopify. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <BlockStack gap="400">
        <BlockStack gap="100">
          <Text variant="headingMd" as="h3">
            Your spend limit
          </Text>
          <Text as="p" tone="subdued">
            The most Better Bundle can charge you in a 30-day cycle. You are
            only ever charged on revenue we attribute to its recommendations,
            so a higher limit costs nothing unless it sells more for you.
          </Text>
        </BlockStack>

        <BlockStack gap="200">
          <InlineStack align="space-between" blockAlign="center">
            <Text as="span" variant="bodySm" tone="subdued">
              {formatCurrency(usageThisCycle)} of{" "}
              {formatCurrency(cappedAmount)} used this cycle
            </Text>
            <Text as="span" variant="bodySm" tone="subdued">
              {Math.round(used * 100)}%
            </Text>
          </InlineStack>
          <ProgressBar
            progress={Math.min(100, Math.round(used * 100))}
            tone={nearLimit ? "critical" : "primary"}
            size="small"
          />
        </BlockStack>

        {nearLimit && (
          <Banner tone="warning">
            <Text as="p">
              You are close to your limit. When it is reached, recommendations
              stop showing until the next cycle or until you raise the limit —
              so you would stop making these sales. Raising it now avoids that.
            </Text>
          </Banner>
        )}

        <BlockStack gap="200">
          <CapSlider
            label="New limit"
            value={draftCap}
            onChange={setDraftCap}
            commissionRate={commissionRate}
            shopCurrency={shopCurrency}
            disabled={submitting}
          />

          {error && (
            <Banner tone="critical">
              <Text as="p">{error}</Text>
            </Banner>
          )}

          <InlineStack align="end">
            <Button
              variant="primary"
              loading={submitting}
              disabled={draftCap === cappedAmount}
              onClick={requestNewCap}
            >
              {draftCap === cappedAmount
                ? "This is your current limit"
                : `Change limit to ${formatCurrency(draftCap)}`}
            </Button>
          </InlineStack>

          <Text as="p" variant="bodySm" tone="subdued">
            Shopify will ask you to approve the new limit before it takes
            effect.
          </Text>
        </BlockStack>
      </BlockStack>
    </Card>
  );
}
