// features/settings/components/SettingsPage.tsx
import { useCallback, useMemo, useState } from "react";
import { useFetcher } from "@remix-run/react";
import {
  Box,
  Page,
  Card,
  BlockStack,
  Text,
  Checkbox,
  Banner,
  Button,
  InlineStack,
  Badge,
  TextField,
  EmptyState,
  Tabs,
} from "@shopify/polaris";
import { NOTHING_FOUND } from "../../../components/UI/illustrations";
import { TitleBar } from "@shopify/app-bridge-react";
import {
  SURFACE_LABELS,
  SURFACE_DESCRIPTIONS,
  type SurfaceKey,
  type SettingsProduct,
} from "../types/settings.types";

interface SettingsPageProps {
  shopCurrency: string;
  initialSurfaces: Record<SurfaceKey, boolean>;
  initialHoldoutDisabled: boolean;
  initialExcludedProductIds: string[];
  products: SettingsProduct[];
  error?: string;
}

const SURFACE_EMOJI: Record<SurfaceKey, string> = {
  mercury: "🛒",
  apollo: "⚡",
  thank_you: "🎉",
  phoenix: "🏪",
  venus: "👤",
};

const SURFACE_ORDER: SurfaceKey[] = [
  "phoenix",
  "mercury",
  "thank_you",
  "apollo",
  "venus",
];

export function SettingsPage({
  shopCurrency,
  initialSurfaces,
  initialHoldoutDisabled,
  initialExcludedProductIds,
  products,
  error,
}: SettingsPageProps) {
  const [surfaces, setSurfaces] =
    useState<Record<SurfaceKey, boolean>>(initialSurfaces);
  const [holdoutDisabled, setHoldoutDisabled] = useState(
    initialHoldoutDisabled,
  );
  const [excludedProductIds, setExcludedProductIds] = useState<string[]>(
    initialExcludedProductIds,
  );
  // useFetcher, not a bare fetch(): with `v3_singleFetch: false` a plain POST
  // to a route path is a *document* request, so Remix runs the action and then
  // renders the whole route as HTML. `response.json()` then threw on the
  // doctype and every save looked like a failure. The fetcher adds the `_data`
  // parameter that makes Remix return the action's JSON instead.
  const fetcher = useFetcher<{
    success?: boolean;
    error?: string;
    /** Whether the storefront flag reached the theme. See saveResult below. */
    mirrored?: boolean;
  }>();
  const saving = fetcher.state !== "idle";

  // What the merchant is told after a save.
  //
  // Serving decisions take effect on the next request, but the *storefront*
  // block is Liquid: it reads a metafield to decide whether to render at all,
  // and Shopify's copy of that value can lag a change by up to an hour or so.
  // So "saved" is true immediately while "gone from my product pages" is not,
  // and saying only the first invites a merchant to switch phoenix off, reload
  // their store, still see the widget, and conclude the toggle is broken.
  //
  // `mirrored: false` means the metafield write itself failed. Recommendations
  // still stop being served — the API is the authority — but the block will
  // keep rendering its placeholder until a later save gets through.
  const saveResult = (() => {
    if (saving || !fetcher.data) return null;

    if (!fetcher.data.success) {
      return {
        tone: "critical" as const,
        message: fetcher.data.error || "Failed to save settings.",
      };
    }

    if (!surfaces.phoenix && fetcher.data.mirrored === false) {
      return {
        tone: "warning" as const,
        message:
          "Settings saved — storefront recommendations have stopped being " +
          "served. We couldn't update your theme, though, so the placeholder " +
          "may keep appearing on product pages. Saving again usually fixes it.",
      };
    }

    if (!surfaces.phoenix) {
      return {
        tone: "success" as const,
        message:
          "Settings saved. Storefront recommendations have stopped " +
          "immediately; your product pages can take up to an hour to stop " +
          "showing the placeholder, because Shopify caches theme data.",
      };
    }

    return {
      tone: "success" as const,
      message: "Settings saved. Changes apply to new requests immediately.",
    };
  })();
  const [activeTab, setActiveTab] = useState(0);

  const [search, setSearch] = useState("");

  const filteredProducts = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return products;
    return products.filter((p) => p.title.toLowerCase().includes(q));
  }, [products, search]);

  const excludedCount = excludedProductIds.length;
  const surfacesOn = Object.values(surfaces).filter(Boolean).length;

  const toggleSurface = useCallback((key: SurfaceKey) => {
    setSurfaces((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const toggleExclusion = useCallback((productId: string) => {
    setExcludedProductIds((prev) =>
      prev.includes(productId)
        ? prev.filter((id) => id !== productId)
        : [...prev, productId],
    );
  }, []);

  const handleSave = useCallback(() => {
    fetcher.submit(
      { surfaces, holdoutDisabled, excludedProductIds },
      { method: "POST", encType: "application/json" },
    );
  }, [fetcher, surfaces, holdoutDisabled, excludedProductIds]);

  const tabs = [
    { id: "surfaces", content: "🎛️ Surfaces" },
    { id: "measurement", content: "🧪 Measurement" },
    { id: "exclusions", content: "🚫 Exclusions" },
  ];

  return (
    <Page
      title="Settings"
      subtitle="Choose where recommendations appear, how they're measured, and which products to exclude."
    >
      <TitleBar title="Settings" />
      <BlockStack gap="300">

        {error && (
          <Banner tone="critical">
            <Text as="p" variant="bodyMd" tone="critical">
              {error}
            </Text>
          </Banner>
        )}

        {saveResult && (
          <Banner tone={saveResult.tone}>
            <Text as="p" variant="bodyMd">
              {saveResult.message}
            </Text>
          </Banner>
        )}

        <Tabs
          tabs={tabs}
          selected={activeTab}
          onSelect={setActiveTab}
          fitted
        >
          <div style={{ padding: "16px 0" }}>
            {activeTab === 0 && (
              <SurfacesTab
                surfaces={surfaces}
                surfacesOn={surfacesOn}
                onToggleSurface={toggleSurface}
              />
            )}
            {activeTab === 1 && (
              <MeasurementTab
                holdoutDisabled={holdoutDisabled}
                shopCurrency={shopCurrency}
                onToggleHoldout={(checked) => setHoldoutDisabled(!checked)}
              />
            )}
            {activeTab === 2 && (
              <ExclusionsTab
                filteredProducts={filteredProducts}
                excludedProductIds={excludedProductIds}
                excludedCount={excludedCount}
                search={search}
                onSearch={setSearch}
                onToggleExclusion={toggleExclusion}
              />
            )}
          </div>
        </Tabs>

        <InlineStack align="end">
          <Button variant="primary" onClick={handleSave} loading={saving}>
            Save settings
          </Button>
        </InlineStack>
      </BlockStack>
    </Page>
  );
}

function SurfacesTab({
  surfaces,
  surfacesOn,
  onToggleSurface,
}: {
  surfaces: Record<SurfaceKey, boolean>;
  surfacesOn: number;
  onToggleSurface: (key: SurfaceKey) => void;
}) {
  return (
    <BlockStack gap="500">
      <Card>
        <BlockStack gap="300">
          <InlineStack align="space-between" blockAlign="center">
            <BlockStack gap="100">
              <Text variant="headingMd" as="h3">
                🎛️ Recommendation Surfaces
              </Text>
              <Text as="p" tone="subdued">
                Turn surfaces off to hide recommendations there — the widget
                stays installed but shows nothing.
              </Text>
            </BlockStack>
            <Badge tone="info" size="large">
              {`${surfacesOn} of 5 on`}
            </Badge>
          </InlineStack>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: "12px",
            }}
          >
            {SURFACE_ORDER.map((key) => {
              const enabled = surfaces[key];
              return (
                <Box
                  key={key}
                  padding="400"
                  background={
                    enabled ? "bg-surface-success" : "bg-surface-secondary"
                  }
                  borderRadius="300"
                >
                  <div
                    style={{
                      fontSize: "22px",
                      lineHeight: 1,
                      flexShrink: 0,
                      marginTop: "2px",
                    }}
                  >
                    {SURFACE_EMOJI[key]}
                  </div>
                  <div style={{ flex: 1 }}>
                    <BlockStack gap="050">
                      <InlineStack align="space-between" blockAlign="center">
                        <Text as="p" variant="bodyMd" fontWeight="semibold">
                          {SURFACE_LABELS[key]}
                        </Text>
                        <Checkbox
                          checked={enabled}
                          onChange={() => onToggleSurface(key)}
                          label={SURFACE_LABELS[key]}
                          labelHidden
                        />
                      </InlineStack>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {SURFACE_DESCRIPTIONS[key]}
                      </Text>
                      {/* Only the storefront surface is a Liquid theme block,
                          so it is the only one whose "off" takes a while to
                          show up on the shop. Saying so here — on the toggle
                          itself — is what stops it reading as a broken switch
                          when the widget is still there on the next reload. */}
                      {key === "phoenix" && !enabled && (
                        <Text as="p" variant="bodySm" tone="subdued">
                          Stops serving immediately. Product pages can take up
                          to an hour to stop showing the placeholder.
                        </Text>
                      )}
                    </BlockStack>
                  </div>
                </Box>
              );
            })}
          </div>
        </BlockStack>

      </Card>
    </BlockStack>
  );
}

function MeasurementTab({
  holdoutDisabled,
  shopCurrency,
  onToggleHoldout,
}: {
  holdoutDisabled: boolean;
  shopCurrency: string;
  onToggleHoldout: (checked: boolean) => void;
}) {
  return (
    <BlockStack gap="500">
      <Card>
        <BlockStack gap="300">
          <InlineStack align="space-between" blockAlign="center">
            <BlockStack gap="100">
              <Text variant="headingMd" as="h3">
                🧪 Revenue Measurement
              </Text>
              <Text as="p" tone="subdued">
                A small % of shoppers see no offers (control group) so we can
                measure the true revenue lift your recommendations drive.
              </Text>
            </BlockStack>
            <Checkbox
              checked={!holdoutDisabled}
              onChange={onToggleHoldout}
              label="Holdout testing"
            />
          </InlineStack>

          <Box
            padding="400"
            background={
              holdoutDisabled ? "bg-surface-warning" : "bg-surface-success"
            }
            borderRadius="300"
          >
            <InlineStack align="space-between" blockAlign="center">
              <Text as="p" variant="bodyMd" fontWeight="medium">
                {holdoutDisabled
                  ? "Holdout is off — impact is estimated, not measured against a control."
                  : "Control group active — revenue is measured against shoppers who saw generic recommendations."}
              </Text>
              <Badge tone={holdoutDisabled ? "attention" : "success"}>
                {holdoutDisabled ? "Off" : "Active"}
              </Badge>
            </InlineStack>
          </Box>
        </BlockStack>

      </Card>
    </BlockStack>
  );
}

function ExclusionsTab({
  filteredProducts,
  excludedProductIds,
  excludedCount,
  search,
  onSearch,
  onToggleExclusion,
}: {
  filteredProducts: SettingsProduct[];
  excludedProductIds: string[];
  excludedCount: number;
  search: string;
  onSearch: (value: string) => void;
  onToggleExclusion: (productId: string) => void;
}) {
  return (
    <BlockStack gap="500">
      <Card>
        <BlockStack gap="300">
          <InlineStack align="space-between" blockAlign="center">
            <BlockStack gap="100">
              <Text variant="headingMd" as="h3">
                🚫 Excluded Products
              </Text>
              <Text as="p" tone="subdued">
                These products will never be recommended — great for gift
                cards, low-margin items, or products you'd rather not upsell.
              </Text>
            </BlockStack>
            {excludedCount > 0 && (
              <Badge tone="attention" size="large">
                {`${excludedCount} excluded`}
              </Badge>
            )}
          </InlineStack>

          <TextField
            label="Search products"
            value={search}
            onChange={onSearch}
            autoComplete="off"
            placeholder="Search your catalog to exclude products..."
          />

          {filteredProducts.length === 0 ? (
            <EmptyState
              heading="No products match"
              image={NOTHING_FOUND}
              children={
                <Text as="p" variant="bodySm" tone="subdued">
                  {search
                    ? "Try a different search."
                    : "No products synced yet. Analysis needs to complete before products appear here."}
                </Text>
              }
            />
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
                gap: "8px",
                maxHeight: "320px",
                overflowY: "auto",
                padding: "4px",
              }}
            >
              {filteredProducts.slice(0, 200).map((product) => {
                const excluded = excludedProductIds.includes(
                  product.productId,
                );
                return (
                  <div
                    key={product.productId}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "8px",
                      border: excluded
                        ? "2px solid #FCA5A5"
                        : "1px solid #e5e7eb",
                      borderRadius: "8px",
                      background: excluded ? "#FEF2F2" : "#FAFAFA",
                    }}
                  >
                    {product.imageUrl ? (
                      <img
                        src={product.imageUrl}
                        alt=""
                        width="32"
                        height="32"
                        style={{
                          borderRadius: "4px",
                          objectFit: "cover",
                          flexShrink: 0,
                        }}
                      />
                    ) : (
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: 4,
                          background: "#E5E7EB",
                          flexShrink: 0,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 12,
                          color: "#6B7280",
                        }}
                      >
                        {product.title.charAt(0).toUpperCase()}
                      </div>
                    )}
                    <Text
                      as="p"
                      variant="bodySm"
                      fontWeight={excluded ? "semibold" : "regular"}
                    >
                      {product.title}
                    </Text>
                    <div style={{ marginLeft: "auto" }}>
                      <Checkbox
                        checked={excluded}
                        onChange={() => onToggleExclusion(product.productId)}
                        label={product.title}
                        labelHidden
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </BlockStack>

      </Card>
    </BlockStack>
  );
}