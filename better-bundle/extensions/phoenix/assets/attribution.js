/**
 * Phoenix attribution.
 *
 * Storefront recommendations cannot be attributed the way checkout offers are.
 * At checkout the shopper accepts an offer in the moment, so the extension
 * reports the outcome and the revenue synchronously. On a product page the
 * shopper usually clicks through to the recommended product's own page and adds
 * it there with the theme's own button — an add this app never observes, on a
 * page load Phoenix does not control.
 *
 * So two mechanisms, strongest first:
 *
 *   1. STAMP  When Phoenix itself performs the add, the impression id goes onto
 *             the cart line as `_bb_rec_impression_id`. Shopify promotes it to
 *             the order line and the backend reads it from
 *             `line_item_data.properties`. Deterministic, and it survives
 *             navigation, a closed tab, and days of delay.
 *
 *   2. CLICK  When the shopper clicks through instead, the click is reported
 *             against the impression. The backend later checks whether the
 *             recommended product appears in a paid order within the window.
 *             This over-credits — some of those shoppers were headed there
 *             anyway — which is what the held-out control group exists to
 *             correct.
 *
 * Replaces the old analytics layer, which bootstrapped a session and posted
 * every view and click to `/api/interaction/track`. Both endpoints are gone:
 * the impression row is written server-side when recommendations are served, so
 * there is nothing to correlate a session against.
 */

class PhoenixAttribution {
  constructor() {
    // config.js defines getBaseUrl and is loaded before this file, so there is
    // no fallback literal here — one URL, in one place.
    this.baseUrl = window.getBaseUrl();
    this.logger = window.phoenixLogger || console;
    this.phoenixJWT = null;
    // Outcomes already reported, so a double-click or a re-render cannot
    // report the same impression twice.
    this.reported = new Set();
  }

  setPhoenixJWT(phoenixJWT) {
    this.phoenixJWT = phoenixJWT;
  }

  /**
   * Line item properties that carry attribution onto the order.
   *
   * `_bb_rec_impression_id` is the one that matters — everything else is
   * diagnostic. Keys are prefixed with `_` so Shopify hides them from the
   * customer's cart and order display.
   */
  cartProperties({ impressionId, productId, context, position, quantity }) {
    if (!impressionId) {
      // Without an impression there is nothing to attribute to. Returning
      // empty rather than a half-filled stamp keeps a bad row out of the
      // attribution path entirely.
      this.logger.warn("Phoenix: add-to-cart with no impression_id");
      return {};
    }
    return {
      _bb_rec_impression_id: String(impressionId),
      _bb_rec_extension: "phoenix",
      _bb_rec_product_id: String(productId || ""),
      _bb_rec_context: String(context || ""),
      _bb_rec_position: String(position ?? ""),
      _bb_rec_quantity: String(quantity || 1),
    };
  }

  /**
   * Report a terminal outcome for an impression.
   *
   * Fire-and-forget: attribution must never block a cart add or a navigation.
   * `keepalive` lets the request survive the page unload that follows a
   * click-through, which is exactly when the click report is sent.
   */
  async report(impressionId, outcome, revenueAdded) {
    if (!impressionId) return false;

    const key = `${impressionId}:${outcome}`;
    if (this.reported.has(key)) return false;
    this.reported.add(key);

    const body = { impression_id: String(impressionId), outcome };
    if (revenueAdded != null && Number(revenueAdded) > 0) {
      body.revenue_added = Number(revenueAdded);
    }

    const url = `${this.baseUrl}/api/interaction/outcome`;
    try {
      if (this.phoenixJWT && this.phoenixJWT.isReady()) {
        await this.phoenixJWT.makeAuthenticatedRequest(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          keepalive: true,
        });
      } else {
        await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          keepalive: true,
        });
      }
      return true;
    } catch (error) {
      // A lost outcome costs attribution on one order, never the sale. The
      // stamp path also still covers adds Phoenix performed itself.
      this.logger.warn(`Phoenix: outcome '${outcome}' not reported:`, error);
      this.reported.delete(key);
      return false;
    }
  }

  /** Shopper clicked through to the recommended product's own page. */
  reportClick(impressionId) {
    return this.report(impressionId, "clicked");
  }

  /** Shopper added the recommendation from the widget itself. */
  reportAccepted(impressionId, revenueAdded) {
    return this.report(impressionId, "accepted", revenueAdded);
  }

  /** Shopper explicitly dismissed the offer, where a surface offers that. */
  reportDeclined(impressionId) {
    return this.report(impressionId, "declined");
  }
}

window.PhoenixAttribution = PhoenixAttribution;
window.phoenixAttribution = new PhoenixAttribution();
