// features/settings/components/SettingsPage.tsx
import { useCallback, useMemo, useState } from "react";
import {
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
import { TitleBar } from "@shopify/app-bridge-react";
import { HeroHeader } from "../../../components/UI/HeroHeader";
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
  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState<{
    tone: "success" | "critical";
    message: string;
  } | null>(null);
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

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaveResult(null);
    try {
      const response = await fetch("/app/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          surfaces,
          holdoutDisabled,
          excludedProductIds,
        }),
      });
      const result = await response.json();
      if (result.success) {
        setSaveResult({
          tone: "success",
          message: "Settings saved. Changes apply to new requests immediately.",
        });
      } else {
        setSaveResult({
          tone: "critical",
          message: result.error || "Failed to save settings.",
        });
      }
    } catch {
      setSaveResult({
        tone: "critical",
        message: "Failed to save settings. Please try again.",
      });
    } finally {
      setSaving(false);
    }
  }, [surfaces, holdoutDisabled, excludedProductIds]);

  const tabs = [
    { id: "surfaces", content: "🎛️ Surfaces" },
    { id: "measurement", content: "🧪 Measurement" },
    { id: "exclusions", content: "🚫 Exclusions" },
  ];

  return (
    <Page>
      <TitleBar title="Settings" />
      <BlockStack gap="300">
        <HeroHeader
          title="Control where and how recommendations appear"
          subtitle="Choose which surfaces show offers, how revenue is measured, and which products are never recommended."
          variant="subtle"
          align="left"
        />

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
        <div style={{ padding: "24px" }}>
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
                  <div
                    key={key}
                    style={{
                      padding: "16px",
                      backgroundColor: enabled ? "#F0FDF4" : "#FAFAFA",
                      borderRadius: "12px",
                      border: `2px solid ${enabled ? "#BBF7D0" : "#E5E7EB"}`,
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "12px",
                    }}
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
                      </BlockStack>
                    </div>
                  </div>
                );
              })}
            </div>
          </BlockStack>
        </div>
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
        <div style={{ padding: "24px" }}>
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

            <div
              style={{
                padding: "16px",
                backgroundColor: holdoutDisabled ? "#FEF3C7" : "#F0FDF4",
                borderRadius: "12px",
                border: `1px solid ${holdoutDisabled ? "#FCD34D" : "#BBF7D0"}`,
              }}
            >
              <InlineStack align="space-between" blockAlign="center">
                <Text as="p" variant="bodyMd" fontWeight="medium">
                  {holdoutDisabled
                    ? "Holdout is off — impact is estimated, not measured against a control."
                    : `Control group active · ${shopCurrency === "USD" ? "$" : shopCurrency} revenue measured causally`}
                </Text>
                <Badge tone={holdoutDisabled ? "attention" : "success"}>
                  {holdoutDisabled ? "Off" : "Active"}
                </Badge>
              </InlineStack>
            </div>
          </BlockStack>
        </div>
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
        <div style={{ padding: "24px" }}>
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
                image=""
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
        </div>
      </Card>
    </BlockStack>
  );
}