// features/preview/components/PreviewPanel.tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useFetcher } from "@remix-run/react";
import {
  Box,
  Card,
  BlockStack,
  Text,
  Button,
  InlineStack,
  Badge,
  TextField,
  Banner,
  EmptyState,
  Spinner,
  Tabs,
} from "@shopify/polaris";
import { PREVIEW_IDLE } from "../../../components/UI/illustrations";
import type {
  PreviewProduct,
  PreviewResult,
} from "../types/preview.types";

interface PreviewPanelProps {
  shopCurrency: string;
  products: PreviewProduct[];
}

const SURFACE_TABS = [
  { id: "mercury", content: "🛒 Checkout" },
  { id: "apollo", content: "⚡ Post-Purchase" },
  { id: "thank_you", content: "🎉 Thank-You Page" },
  { id: "phoenix", content: "🏪 Storefront" },
  { id: "venus", content: "👤 Customer Account" },
];

export function PreviewPanel({ shopCurrency, products }: PreviewPanelProps) {
  const [activeTab, setActiveTab] = useState(0);
  const [search, setSearch] = useState("");
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  // Same reason as SettingsPage: a bare fetch() to a route path is a document
  // request under `v3_singleFetch: false` and comes back as HTML, so the JSON
  // parse always threw and every preview reported the backend as down.
  const fetcher = useFetcher<PreviewResult & { error?: string }>();
  const loading = fetcher.state !== "idle";
  const [result, setResult] = useState<PreviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const surface = SURFACE_TABS[activeTab]?.id ?? "mercury";

  const filteredProducts = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return products;
    return products.filter((p) => p.title.toLowerCase().includes(q));
  }, [products, search]);

  const toggleProduct = useCallback((productId: string) => {
    setSelectedProductIds((prev) =>
      prev.includes(productId)
        ? prev.filter((id) => id !== productId)
        : [...prev, productId],
    );
  }, []);

  const handleTabChange = useCallback((index: number) => {
    setActiveTab(index);
    // A different surface means a different set of offers — clear the old
    // result so the merchant isn't shown stale recommendations.
    setResult(null);
    setError(null);
  }, []);

  const handlePreview = useCallback(() => {
    if (selectedProductIds.length === 0) return;
    setError(null);
    setResult(null);
    // Posts to the Setup route, which owns the dry-run action. The old
    // /app/preview is a 302 redirect, and a redirected POST would arrive with
    // no body — the preview would silently return nothing.
    fetcher.submit(
      { productIds: selectedProductIds, surface },
      { method: "POST", encType: "application/json", action: "/app/extensions" },
    );
  }, [fetcher, selectedProductIds, surface]);

  // fetcher.data persists across submissions, so key off identity to avoid
  // re-applying the previous response after a tab change cleared the panel.
  const seen = useRef<unknown>(null);
  useEffect(() => {
    if (loading || !fetcher.data || fetcher.data === seen.current) return;
    seen.current = fetcher.data;
    if (fetcher.data.error) setError(fetcher.data.error);
    else setResult(fetcher.data);
  }, [loading, fetcher.data]);

  const selectedProducts = products.filter((p) =>
    selectedProductIds.includes(p.productId),
  );

  return (
    <BlockStack gap="300">
      <BlockStack gap="100">
        <Text as="h2" variant="headingMd">
          Preview what shoppers will see
        </Text>
        <Text as="p" tone="subdued">
          Pick a product and simulate any placement. This is a dry run — it
          records no impression and never reaches a real shopper.
        </Text>
      </BlockStack>

      <Tabs
          tabs={SURFACE_TABS}
          selected={activeTab}
          onSelect={handleTabChange}
          fitted
        >
          <div style={{ padding: "16px 0" }}>
            <BlockStack gap="500">
              {error && (
                <Banner tone="critical">
                  <Text as="p" variant="bodyMd" tone="critical">
                    {error}
                  </Text>
                </Banner>
              )}

              {/* Build cart card */}
              <Card>
                <BlockStack gap="300">
                  <InlineStack align="space-between" blockAlign="center">
                    <BlockStack gap="100">
                      <Text variant="headingMd" as="h3">
                        🛍️ Build a Test Cart
                      </Text>
                      <Text as="p" tone="subdued">
                        Pick products to see what the AI would recommend on
                        this surface.
                      </Text>
                    </BlockStack>
                    <Badge tone="info" size="large">
                      {`${selectedProductIds.length} in cart`}
                    </Badge>
                  </InlineStack>

                  <TextField
                    label="Search products to add to the cart"
                    value={search}
                    onChange={setSearch}
                    autoComplete="off"
                    placeholder="e.g. 'yoga mat'..."
                  />

                  {filteredProducts.length === 0 ? (
                    <EmptyState
                      heading="No products match"
                      image={PREVIEW_IDLE}
                      children={
                        <Text as="p" variant="bodySm" tone="subdued">
                          {search
                            ? "Try a different search."
                            : "No products synced yet. Analysis needs to complete first."}
                        </Text>
                      }
                    />
                  ) : (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns:
                          "repeat(auto-fill, minmax(220px, 1fr))",
                        gap: "8px",
                        maxHeight: "260px",
                        overflowY: "auto",
                        padding: "4px",
                      }}
                    >
                      {filteredProducts.slice(0, 100).map((product) => {
                        const selected = selectedProductIds.includes(
                          product.productId,
                        );
                        return (
                          <button
                            key={product.productId}
                            type="button"
                            onClick={() => toggleProduct(product.productId)}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                              padding: "8px",
                              border: selected
                                ? "2px solid #008060"
                                : "1px solid #e5e7eb",
                              borderRadius: "8px",
                              background: selected ? "#F0FDF9" : "#FAFAFA",
                              cursor: "pointer",
                              textAlign: "left",
                              fontFamily: "inherit",
                              fontSize: "inherit",
                              color: "inherit",
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
                              fontWeight={selected ? "semibold" : "regular"}
                            >
                              {product.title}
                            </Text>
                          </button>
                        );
                      })}
                    </div>
                  )}

                  {selectedProducts.length > 0 && (
                    <Box padding="400" background="bg-surface-success" borderRadius="300">
                      <InlineStack
                        align="space-between"
                        blockAlign="center"
                        gap="200"
                      >
                        <Text as="p" variant="bodySm" fontWeight="semibold">
                          🛒 Cart:{" "}
                          {selectedProducts.map((p) => p.title).join(", ")}
                        </Text>
                        <Button
                          variant="primary"
                          onClick={handlePreview}
                          loading={loading}
                          size="medium"
                        >
                          {loading ? "Fetching..." : "Preview recommendations"}
                        </Button>
                      </InlineStack>
                    </Box>
                  )}
                </BlockStack>

              </Card>

              {loading && (
                <Card>
                  <BlockStack gap="200" inlineAlign="center">
                    <Spinner
                      accessibilityLabel="Fetching recommendations"
                      size="large"
                    />
                    <Text as="p" variant="bodyMd" tone="subdued">
                      Asking the recommendation engine...
                    </Text>
                  </BlockStack>
                </Card>
              )}

              {result && !loading && (
                <Card>
                  <BlockStack gap="400">
                    <InlineStack align="space-between" blockAlign="center">
                      <BlockStack gap="100">
                        <Text variant="headingMd" as="h3">
                          ✨ Recommended for this Cart
                        </Text>
                        <Text as="p" tone="subdued">
                          What shoppers on this surface would be offered right
                          now.
                        </Text>
                      </BlockStack>
                      <Badge
                        tone={result.count > 0 ? "success" : "warning"}
                        size="large"
                      >
                        {`${result.count} offer${result.count === 1 ? "" : "s"}`}
                      </Badge>
                    </InlineStack>

                    {result.count === 0 ? (
                      <Box padding="500" background="bg-surface-warning" borderRadius="300">
                        <Text as="p" variant="bodyMd" tone="subdued">
                          No recommendations for this cart yet. The AI builds
                          edges from product similarity and co-purchase
                          history — try another product or check back after
                          more data.
                        </Text>
                      </Box>
                    ) : (
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns:
                            "repeat(auto-fit, minmax(280px, 1fr))",
                          gap: "12px",
                        }}
                      >
                        {result.items.map((item) => (
                          <div
                            key={item.product_id}
                            style={{
                              padding: "16px",
                              backgroundColor: "#F0FDF4",
                              borderRadius: "12px",
                              border: "1px solid #BBF7D0",
                            }}
                          >
                            <BlockStack gap="200">
                              <Text
                                as="p"
                                variant="bodyMd"
                                fontWeight="semibold"
                              >
                                {item.title}
                              </Text>
                              <Text
                                as="h3"
                                variant="headingLg"
                                fontWeight="bold"
                              >
                                {shopCurrency === "USD" ? "$" : ""}
                                {Number(item.price).toFixed(2)}
                              </Text>
                              <InlineStack gap="100" wrap>
                                <Badge tone="info" size="small">
                                  {item.edge_type}
                                </Badge>
                                <Badge
                                  tone={
                                    item.source === "observed"
                                      ? "success"
                                      : "attention"
                                  }
                                  size="small"
                                >
                                  {item.source === "observed"
                                    ? "Data-driven"
                                    : "AI prior"}
                                </Badge>
                              </InlineStack>
                              {item.observed_count > 0 && (
                                <Text as="p" variant="bodySm" tone="subdued">
                                  Bought together {item.observed_count}×
                                </Text>
                              )}
                            </BlockStack>
                          </div>
                        ))}
                      </div>
                    )}
                  </BlockStack>

                </Card>
              )}
            </BlockStack>
          </div>
      </Tabs>
    </BlockStack>
  );
}