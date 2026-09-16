import {
  Badge,
  BlockStack,
  Card,
  Divider,
  InlineGrid,
  InlineStack,
  Text,
} from "@shopify/polaris";
import { MetricTile } from "../../../components/UI/MetricTile";
import type { SyncStatus } from "../types/home.types";

export function getSyncStatusBadge(sync: SyncStatus): {
  tone: "success" | "attention" | "info";
  label: string;
} {
  if (sync.productsTotal === 0 && sync.ordersTotal === 0) {
    return { tone: "attention", label: "Awaiting initial sync" };
  }
  // A catalog we have only partly ingested is the one thing this badge most
  // needs to surface, and it used to be invisible: every figure here was
  // measured against our own imported rows, so the card read "up to date"
  // with most of the store missing.
  if (isCatalogIncomplete(sync)) {
    return { tone: "attention", label: "Catalog sync incomplete" };
  }
  if (
    sync.productsActive > 0 &&
    sync.productsEmbedded < sync.productsActive
  ) {
    return { tone: "attention", label: "Indexing in progress" };
  }
  return { tone: "success", label: "Up to date" };
}

/** True when Shopify reports more products than we have imported. */
export function isCatalogIncomplete(sync: SyncStatus): boolean {
  return (
    sync.productsInStore != null && sync.productsTotal < sync.productsInStore
  );
}

export function formatLastSynced(
  isoString: string | null,
  now: Date = new Date(),
): string {
  if (!isoString) return "Awaiting initial sync";
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return "Awaiting initial sync";

  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear();

  const timeStr = date.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });

  if (isToday) {
    return `Last updated: Today at ${timeStr}`;
  }

  const dateStr = date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
  return `Last updated: ${dateStr} at ${timeStr}`;
}

export interface SyncStatusCardProps {
  sync: SyncStatus;
}

function productsSubtitle(sync: SyncStatus): string {
  if (sync.productsTotal === 0) return "No products synced yet";
  if (sync.productsInStore == null) {
    return `${sync.productsActive.toLocaleString()} active`;
  }
  const missing = sync.productsInStore - sync.productsTotal;
  if (missing > 0) {
    return `${missing.toLocaleString()} not yet imported from Shopify`;
  }
  return `${sync.productsActive.toLocaleString()} active — full catalog imported`;
}

export function SyncStatusCard({ sync }: SyncStatusCardProps) {
  const badge = getSyncStatusBadge(sync);
  const lastUpdated = formatLastSynced(sync.lastSyncedAt);

  const hasActiveProducts = sync.productsActive > 0;
  const isFullyEmbedded =
    hasActiveProducts && sync.productsEmbedded >= sync.productsActive;
  const embeddingPercent = hasActiveProducts
    ? Math.min(100, Math.round((sync.productsEmbedded / sync.productsActive) * 100))
    : 0;

  let embeddingSub = "No active products to embed";
  if (hasActiveProducts) {
    if (isFullyEmbedded) {
      embeddingSub = "100% catalog embedded for AI recommendations";
    } else {
      embeddingSub = `${embeddingPercent}% catalog embedded (${sync.productsEmbedded.toLocaleString()} of ${sync.productsActive.toLocaleString()})`;
    }
  }

  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack align="space-between" blockAlign="center">
          <BlockStack gap="100">
            <Text variant="headingMd" as="h2">
              Store Data & AI Model Status
            </Text>
            <Text as="p" tone="subdued">
              Your Shopify store catalog and order data synchronized with
              BetterBundle.
            </Text>
          </BlockStack>
          <Badge tone={badge.tone}>{badge.label}</Badge>
        </InlineStack>

        <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="400">
          <MetricTile
            label="Products synced"
            value={
              sync.productsInStore != null
                ? `${sync.productsTotal.toLocaleString()} / ${sync.productsInStore.toLocaleString()}`
                : sync.productsTotal.toLocaleString()
            }
            sub={productsSubtitle(sync)}
            progress={
              sync.productsInStore != null && sync.productsInStore > 0
                ? { value: sync.productsTotal, max: sync.productsInStore }
                : undefined
            }
            tone={isCatalogIncomplete(sync) ? "caution" : undefined}
            tooltip="Products imported from Shopify, against the number your store actually has."
          />

          <MetricTile
            label="AI embeddings"
            value={
              hasActiveProducts
                ? `${sync.productsEmbedded.toLocaleString()} / ${sync.productsActive.toLocaleString()}`
                : "0 / 0"
            }
            sub={embeddingSub}
            progress={
              hasActiveProducts
                ? { value: sync.productsEmbedded, max: sync.productsActive }
                : undefined
            }
            tone={isFullyEmbedded ? "success" : hasActiveProducts ? "caution" : undefined}
            tooltip="Vector embeddings generated by the AI model for semantic and visual similarity recommendations."
          />

          <MetricTile
            label="Collections"
            value={sync.collectionsTotal.toLocaleString()}
            sub={
              sync.collectionsTotal > 0
                ? "Synced and categorized"
                : "No collections found"
            }
            tooltip="Collections synchronized from Shopify used for collection-aware recommendations."
          />

          <MetricTile
            label="Orders processed"
            value={sync.ordersTotal.toLocaleString()}
            sub={`${sync.edgesObserved.toLocaleString()} co-purchase pairs mined`}
            tooltip="Past orders analyzed to detect patterns of products frequently bought together."
          />
        </InlineGrid>

        <Divider />

        <InlineStack align="space-between" blockAlign="center">
          <Text as="span" variant="bodySm" tone="subdued">
            {lastUpdated}
          </Text>
        </InlineStack>
      </BlockStack>
    </Card>
  );
}
