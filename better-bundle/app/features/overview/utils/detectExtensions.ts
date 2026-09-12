import type { SurfaceKey } from "../../../lib/surfaces";

export interface UiExtensionActivation {
  target: string;
}

export interface ThemeAppBlockActivation {
  target: string;
  themeId?: string;
}

export interface ThemeExtensionActivation {
  handle?: string;
  name?: string;
  target?: string;
  status?: "active" | "available" | "unavailable" | string;
  activations?: ThemeAppBlockActivation[];
}

export interface ExtensionInfo {
  handle: string;
  type: "ui_extension" | "theme_app_extension" | string;
  activations?: Array<UiExtensionActivation | ThemeExtensionActivation | any>;
}

export type DetectedSurfaces = Partial<Record<SurfaceKey, boolean>>;

/**
 * Pure parser for `shopify.app.extensions()` output.
 * Evaluates which surfaces are actively installed/placed in Shopify.
 */
export function parseExtensionActivations(
  extensions: ExtensionInfo[],
): DetectedSurfaces {
  const detected: DetectedSurfaces = {
    phoenix: false,
    apollo: false,
    mercury: false,
    thank_you: false,
    venus: false,
  };

  if (!Array.isArray(extensions)) {
    return detected;
  }

  for (const ext of extensions) {
    if (!ext || !Array.isArray(ext.activations)) continue;

    // Mercury handles both Checkout and Thank You page targets
    if (ext.handle === "mercury" || ext.type === "ui_extension") {
      for (const act of ext.activations) {
        const target = typeof act?.target === "string" ? act.target : "";
        if (
          target === "purchase.checkout.payment-method-list.render-before" ||
          target.startsWith("purchase.checkout.")
        ) {
          detected.mercury = true;
        }
        if (
          target === "purchase.thank-you.customer-information.render-after" ||
          target.startsWith("purchase.thank-you.")
        ) {
          detected.thank_you = true;
        }
      }
    }

    // Venus handles Customer Account Order Status page
    if (ext.handle === "venus") {
      for (const act of ext.activations) {
        const target = typeof act?.target === "string" ? act.target : "";
        if (
          target === "customer-account.order-status.block.render" ||
          target.startsWith("customer-account.")
        ) {
          detected.venus = true;
        }
      }
    }

    // Phoenix handles storefront Theme App Extension blocks
    if (ext.handle === "phoenix" || ext.type === "theme_app_extension") {
      for (const act of ext.activations) {
        // App blocks report status: 'active' when placed and enabled in published theme
        if (
          act?.status === "active" ||
          (Array.isArray(act?.activations) && act.activations.length > 0)
        ) {
          detected.phoenix = true;
        }
      }
    }

    // Apollo handles post-purchase
    if (ext.handle === "apollo") {
      if (ext.activations.length > 0) {
        detected.apollo = true;
      }
    }
  }

  return detected;
}

/**
 * Queries the Shopify App Bridge API to detect installed extensions in real time.
 * Returns detected status for each surface, or empty object if not supported/available.
 */
export async function detectInstalledSurfaces(): Promise<{
  detected: DetectedSurfaces;
  supported: boolean;
}> {
  try {
    const shopify =
      typeof window !== "undefined"
        ? (window as any).shopify
        : typeof globalThis !== "undefined"
          ? (globalThis as any).shopify
          : null;

    if (shopify?.app?.extensions && typeof shopify.app.extensions === "function") {
      const extensions = await shopify.app.extensions();
      if (Array.isArray(extensions)) {
        return {
          detected: parseExtensionActivations(extensions),
          supported: true,
        };
      }
    }
  } catch (error) {
    console.warn("Failed to query shopify.app.extensions():", error);
  }

  return { detected: {}, supported: false };
}
