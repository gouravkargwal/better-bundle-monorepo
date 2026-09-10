import {
  BlockStack,
  Box,
  Card,
  Icon,
  InlineStack,
  ProgressBar,
  Text,
  Tooltip,
} from "@shopify/polaris";
import { InfoIcon } from "@shopify/polaris-icons";

/**
 * One number with its label, and — where the term is contestable — a tooltip
 * defining it.
 *
 * Replaces four near-identical hand-rolled stat blocks across Overview, Impact
 * and Billing, each a `<div>` with its own hardcoded background/border hex pair
 * and its own idea of type scale.
 *
 * The tooltip is not decoration. "Attributed revenue", "incremental revenue"
 * and "cap" are the three terms a merchant is most likely to misread, and two
 * of them look identical unless someone explains the difference. Getting that
 * wrong is how the app came to present attributed revenue as proven
 * incremental revenue in the first place.
 */

interface MetricTileProps {
  label: string;
  /** Definition of the term. Supply it whenever the label is jargon. */
  tooltip?: string;
  /** Pre-formatted. Pass an em dash for "no data", never a zero. */
  value: string;
  /** Secondary line under the value. */
  sub?: string;
  /** Renders a progress bar — for trial thresholds and spend caps. */
  progress?: { value: number; max: number };
  tone?: "success" | "critical" | "caution";
}

export function MetricTile({
  label,
  tooltip,
  value,
  sub,
  progress,
  tone,
}: MetricTileProps) {
  const heading = (
    <Text as="span" variant="bodySm" tone="subdued">
      {label}
    </Text>
  );

  const percent =
    progress && progress.max > 0
      ? Math.min(100, Math.max(0, (progress.value / progress.max) * 100))
      : 0;

  return (
    <Card>
      <BlockStack gap="200">
        <InlineStack gap="100" blockAlign="center" wrap={false}>
          {heading}
          {tooltip && (
            <Tooltip content={tooltip}>
              <Box>
                <Icon source={InfoIcon} tone="subdued" />
              </Box>
            </Tooltip>
          )}
        </InlineStack>

        <Text
          as="p"
          variant="headingLg"
          fontWeight="bold"
          tone={tone === "success" ? "success" : tone === "critical" ? "critical" : undefined}
        >
          {value}
        </Text>

        {progress && (
          <ProgressBar
            progress={percent}
            size="small"
            tone={tone === "critical" ? "critical" : "primary"}
          />
        )}

        {sub && (
          <Text as="span" variant="bodySm" tone="subdued">
            {sub}
          </Text>
        )}
      </BlockStack>
    </Card>
  );
}
