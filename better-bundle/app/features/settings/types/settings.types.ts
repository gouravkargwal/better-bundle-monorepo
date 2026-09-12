// features/settings/types/settings.types.ts

/** Surfaces a merchant can toggle from Settings. Keys match the worker's
 *  CONTEXT_SURFACE surface names so the flag maps 1:1 to serving. */
export type SurfaceKey =
  | "mercury" // checkout UI block (Plus) — context checkout_page
  | "apollo" // post-purchase interstitial — context post_purchase
  | "thank_you" // Thank You page block — context thank_you_page
  | "phoenix" // storefront theme blocks — context product_page
  | "venus"; // customer account order status — context order_status

export const SURFACE_LABELS: Record<SurfaceKey, string> = {
  mercury: "Checkout recommendations",
  apollo: "Post-purchase upsells",
  thank_you: "Thank-you page",
  phoenix: "Storefront blocks",
  venus: "Customer account",
};

export const SURFACE_DESCRIPTIONS: Record<SurfaceKey, string> = {
  mercury:
    "Product recommendations shown inside the Shopify checkout. Shopify Plus stores only.",
  apollo:
    "One-click upsell offers shown right after a customer completes their purchase.",
  thank_you:
    "Recommendations on the post-purchase Thank You page — available on every plan.",
  phoenix:
    "AI recommendation blocks placed on your storefront pages (product page and cart page).",
  venus:
    "Personalized recommendations on customer account order status pages.",
};

export interface SettingsState {
  surfaces: Record<SurfaceKey, boolean>;
  excludedProductIds: string[];
  holdoutDisabled: boolean;
  shopCurrency: string;
  shopDomain: string;
}

export interface SettingsProduct {
  productId: string;
  title: string;
  imageUrl: string | null;
}

export interface SettingsError {
  error: string;
}