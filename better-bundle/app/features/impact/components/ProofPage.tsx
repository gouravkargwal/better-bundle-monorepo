import {
  Badge,
  BlockStack,
  Box,
  Card,
  Divider,
  IndexTable,
  InlineStack,
  Page,
  Text,
  Tooltip,
} from "@shopify/polaris";

import { ResultState } from "../../../components/UI/ResultState";
import { SURFACES, type SurfaceKey } from "../../../lib/surfaces";
import type { ProofResult, SurfaceProofRow } from "../types/proof.types";

/**
 * "Did recommendations actually add revenue?" — and an honest answer when we
 * cannot yet tell.
 *
 * Replaces a 521-line route whose headline read "Incremental Revenue, measured
 * against the control group · 95% CI" over a figure that was in fact attributed
 * revenue, beside a literal p-value.
 */

interface ProofPageProps {
  summary: ProofResult;
  bySurface: SurfaceProofRow[];
  currencyCode: string;
  holdoutPercent: number;
  windowDays: number;
}

const BADGE: Record<
  ProofResult["state"],
  { tone: "success" | "info" | "attention" | "warning" | undefined; label: string }
> = {
  significant: { tone: "success", label: "Measured lift" },
  not_significant: { tone: "attention", label: "No clear difference" },
  insufficient_data: { tone: "info", label: "Collecting" },
  not_measurable: { tone: undefined, label: "Not measurable" },
  holdout_disabled: { tone: "warning", label: "Measurement off" },
  unavailable: { tone: undefined, label: "Unavailable" },
};

function liftCell(result: ProofResult): string {
  // A number here only when it has been earned. An em dash rather than "0%",
  // which a merchant reads as "it did nothing".
  if (result.state === "significant" || result.state === "not_significant") {
    return `${(result.conversionLiftRel * 100).toFixed(1)}%`;
  }
  return "—";
}

function confidenceCell(result: ProofResult): string {
  if (result.state === "significant") {
    return `p = ${result.pValue.toFixed(3)}`;
  }
  if (result.state === "not_significant") {
    return `p = ${result.pValue.toFixed(2)}`;
  }
  return "—";
}

function controlOrdersCell(result: ProofResult): string {
  if (result.state === "insufficient_data") {
    return `${result.controlConverters} of ${result.minControlOrders}`;
  }
  if (result.state === "significant" || result.state === "not_significant") {
    return String(result.control.converters);
  }
  return "—";
}

export function ProofPage({
  summary,
  bySurface,
  currencyCode,
  holdoutPercent,
  windowDays,
}: ProofPageProps) {
  const window = `the last ${windowDays} days`;

  const rows = bySurface.map((row, index) => {
    const meta = SURFACES[row.surface as SurfaceKey];
    const badge = BADGE[row.result.state];

    const label = (
      <InlineStack gap="200" blockAlign="center">
        <Text as="span" fontWeight="semibold">
          {row.label}
        </Text>
        {meta?.plusOnly && <Badge>Plus</Badge>}
      </InlineStack>
    );

    return (
      <IndexTable.Row id={row.surface} key={row.surface} position={index}>
        <IndexTable.Cell>{label}</IndexTable.Cell>
        <IndexTable.Cell>
          {row.result.state === "not_measurable" ? (
            <Tooltip content="Shown to every shopper by design — there is no control group here to compare against.">
              <Badge tone={badge.tone}>{badge.label}</Badge>
            </Tooltip>
          ) : (
            <Badge tone={badge.tone}>{badge.label}</Badge>
          )}
        </IndexTable.Cell>
        <IndexTable.Cell>
          <Text as="span" numeric>
            {liftCell(row.result)}
          </Text>
        </IndexTable.Cell>
        <IndexTable.Cell>
          <Text as="span" tone="subdued" numeric>
            {confidenceCell(row.result)}
          </Text>
        </IndexTable.Cell>
        <IndexTable.Cell>
          <Text as="span" tone="subdued" numeric>
            {controlOrdersCell(row.result)}
          </Text>
        </IndexTable.Cell>
      </IndexTable.Row>
    );
  });

  return (
    <Page
      title="Proof"
      subtitle="Whether recommendations added revenue you wouldn't have had otherwise."
    >
      <BlockStack gap="400">
        <Card>
          <ResultState
            result={summary}
            currencyCode={currencyCode}
            holdoutPercent={holdoutPercent}
            window={window}
          />
        </Card>

        <Card padding="0">
          <Box padding="400" paddingBlockEnd="200">
            <Text as="h2" variant="headingMd">
              By placement
            </Text>
          </Box>
          <IndexTable
            resourceName={{ singular: "placement", plural: "placements" }}
            itemCount={rows.length}
            selectable={false}
            headings={[
              { title: "Placement" },
              { title: "Result" },
              { title: "Lift" },
              { title: "Confidence" },
              { title: "Control orders" },
            ]}
          >
            {rows}
          </IndexTable>
        </Card>

        <Card>
          <BlockStack gap="300">
            <Text as="h2" variant="headingMd">
              How this is measured
            </Text>
            <Divider />
            <BlockStack gap="200">
              <Text as="p">
                <Text as="span" fontWeight="semibold">
                  Attributed revenue
                </Text>{" "}
                — orders where a shopper interacted with a recommendation. It
                comes from a stamp on the order line, so it is exact. This is
                what your 3% is calculated on, and you can see it on Home.
              </Text>
              <Text as="p">
                <Text as="span" fontWeight="semibold">
                  Incremental revenue
                </Text>{" "}
                — how much <em>more</em> those shoppers spent than the{" "}
                {holdoutPercent}% control group who were shown nothing. This is
                a statistical estimate, it needs enough orders to be reliable,
                and it is always smaller than attributed revenue.
              </Text>
              <Text as="p" tone="subdued">
                We hold back {holdoutPercent}% of shoppers from seeing
                recommendations so there is always something to compare against.
                Without that control group there is no way to tell a sale you
                caused from one that would have happened anyway — so we would
                rather say "we can't tell yet" than show you a number we can't
                stand behind.
              </Text>
            </BlockStack>
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
