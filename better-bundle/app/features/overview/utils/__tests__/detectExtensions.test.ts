import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  parseExtensionActivations,
  detectInstalledSurfaces,
  type ExtensionInfo,
} from "../detectExtensions";

describe("parseExtensionActivations", () => {
  it("returns all false when input is empty or invalid", () => {
    expect(parseExtensionActivations([])).toEqual({
      phoenix: false,
      apollo: false,
      mercury: false,
      thank_you: false,
      venus: false,
    });

    expect(parseExtensionActivations(null as any)).toEqual({
      phoenix: false,
      apollo: false,
      mercury: false,
      thank_you: false,
      venus: false,
    });
  });

  it("detects mercury checkout and thank-you targets", () => {
    const extensions: ExtensionInfo[] = [
      {
        handle: "mercury",
        type: "ui_extension",
        activations: [
          { target: "purchase.checkout.payment-method-list.render-before" },
          { target: "purchase.thank-you.customer-information.render-after" },
        ],
      },
    ];

    const result = parseExtensionActivations(extensions);
    expect(result.mercury).toBe(true);
    expect(result.thank_you).toBe(true);
    expect(result.venus).toBe(false);
    expect(result.phoenix).toBe(false);
  });

  it("detects venus customer account target", () => {
    const extensions: ExtensionInfo[] = [
      {
        handle: "venus",
        type: "ui_extension",
        activations: [
          { target: "customer-account.order-status.block.render" },
        ],
      },
    ];

    const result = parseExtensionActivations(extensions);
    expect(result.venus).toBe(true);
    expect(result.mercury).toBe(false);
  });

  it("detects phoenix active theme app block", () => {
    const extensions: ExtensionInfo[] = [
      {
        handle: "phoenix",
        type: "theme_app_extension",
        activations: [
          {
            handle: "Product-optimal",
            status: "active",
            target: "section",
            activations: [
              {
                target: "template--product/main/Product-optimal",
                themeId: "gid://shopify/OnlineStoreTheme/1",
              },
            ],
          },
        ],
      },
    ];

    const result = parseExtensionActivations(extensions);
    expect(result.phoenix).toBe(true);
  });

  it("detects apollo post-purchase extension", () => {
    const extensions: ExtensionInfo[] = [
      {
        handle: "apollo",
        type: "ui_extension",
        activations: [
          { target: "purchase.post-purchase.render" },
        ],
      },
    ];

    const result = parseExtensionActivations(extensions);
    expect(result.apollo).toBe(true);
  });
});

describe("detectInstalledSurfaces", () => {
  const originalShopify = (globalThis as any).shopify;

  beforeEach(() => {
    delete (globalThis as any).shopify;
  });

  afterEach(() => {
    if (originalShopify) {
      (globalThis as any).shopify = originalShopify;
    } else {
      delete (globalThis as any).shopify;
    }
  });

  it("returns supported: false when shopify.app.extensions is not available", async () => {
    const result = await detectInstalledSurfaces();
    expect(result.supported).toBe(false);
    expect(result.detected).toEqual({});
  });

  it("calls shopify.app.extensions() and parses response when available", async () => {
    (globalThis as any).shopify = {
      app: {
        extensions: vi.fn().mockResolvedValue([
          {
            handle: "mercury",
            type: "ui_extension",
            activations: [
              { target: "purchase.thank-you.customer-information.render-after" },
            ],
          },
          {
            handle: "venus",
            type: "ui_extension",
            activations: [
              { target: "customer-account.order-status.block.render" },
            ],
          },
        ]),
      },
    };

    const result = await detectInstalledSurfaces();
    expect(result.supported).toBe(true);
    expect(result.detected.thank_you).toBe(true);
    expect(result.detected.venus).toBe(true);
    expect(result.detected.mercury).toBe(false);
  });
});
