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

    // Consent-gated visitor id. The backend attaches it only if the impression
    // has none, which is how a checkout or thank-you offer — written with no
    // session and no customer — gains the join key its later order needs.
    // Null when the shopper declined measurement, in which case the click stays
    // unattributable, which is the correct outcome rather than a fallback.
    const visitorId = window.bbGetVisitorId ? window.bbGetVisitorId() : null;
    if (visitorId) {
      body.session_id = visitorId;
    }
    if (window.customerId) {
      body.customer_id = String(window.customerId);
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

  /**
   * Record a followed recommendation on the cart itself.
   *
   * This is the durable half of click attribution. Reporting the click updates
   * our own row, but nothing connects that row to an order the shopper places
   * later — the checkout and thank-you surfaces write impressions with no
   * session and no customer, and a guest order has neither either.
   *
   * A cart attribute closes that gap using Shopify's own plumbing: attributes
   * are promoted to `order.note_attributes` and arrive in the order webhook as
   * server-side fact. No cookie, nothing for a privacy tool to strip, and it
   * survives the shopper moving to another device mid-journey.
   *
   * Stores `impressionId:productId` pairs so the backend can check each claim
   * against what the order actually contains, and credit only the products
   * really bought.
   */
  async recordClickOnCart(impressionId, productId) {
    if (!impressionId) return false;

    try {
      // Read first: the value accumulates across a shopping session, and other
      // apps write to the same attribute map. /cart/update.js merges the keys
      // you send rather than replacing the map, so only ours are touched.
      const cartResponse = await fetch("/cart.js", {
        headers: { Accept: "application/json" },
      });
      if (!cartResponse.ok) return false;
      const cart = await cartResponse.json();
      const existing = (cart.attributes && cart.attributes._bb_clicks) || "";

      const pairs = existing
        .split(",")
        .map((pair) => pair.trim())
        .filter(Boolean);

      // Already recorded — a reload or a second visit to the same link.
      if (pairs.some((pair) => pair.split(":")[0] === String(impressionId))) {
        return true;
      }

      pairs.push(`${impressionId}:${productId || ""}`);

      // Bounded. Cart attribute values are not unlimited, and a shopper who
      // browses all afternoon should not eventually break their own checkout.
      // Oldest dropped first: a recent click is the more plausible cause.
      const MAX_RECORDED_CLICKS = 15;
      const trimmed = pairs.slice(-MAX_RECORDED_CLICKS);

      const attributes = { _bb_clicks: trimmed.join(",") };

      // Same write carries the visitor id, which is what lets the *other*
      // attribution paths join this order to impressions at all. It is the
      // identity the backend has always looked for on the order and that
      // nothing ever wrote.
      const visitorId = window.bbGetVisitorId ? window.bbGetVisitorId() : null;
      if (visitorId) {
        attributes._bb_session = visitorId;
      }

      const updateResponse = await fetch("/cart/update.js", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ attributes }),
      });
      return updateResponse.ok;
    } catch (error) {
      // A cart write must never break a product page. The click report already
      // went out, so path 3 can still correlate it if this failed.
      this.logger.warn("Phoenix: could not record click on cart", error);
      return false;
    }
  }
}

window.PhoenixAttribution = PhoenixAttribution;
window.phoenixAttribution = new PhoenixAttribution();

/**
 * Claim a recommendation the shopper followed here from another surface.
 *
 * The thank-you block and the customer-account block can only link out to a
 * product's own page — they have no cart to write to. The shopper then adds the
 * product with the *theme's* button, which this app never sees, so there is no
 * cart line to stamp an impression onto.
 *
 * The recommendation link therefore carries `_bb_imp=<impression id>`. Reading
 * it here reports the click and, more importantly, hands the impression this
 * page's visitor id — giving the clicked-then-bought reconciliation the join
 * key it needs when the order lands.
 *
 * Idempotent per impression: `report()` dedupes in memory, and sessionStorage
 * covers a reload, which would otherwise re-report on every refresh of a URL
 * the shopper may keep in a tab for days.
 */
(function claimImpressionFromUrl() {
  try {
    const params = new URLSearchParams(window.location.search);
    const impressionId = params.get("_bb_imp");
    if (!impressionId) return;

    const seenKey = `bb_claimed_${impressionId}`;
    if (window.sessionStorage && window.sessionStorage.getItem(seenKey)) return;
    if (window.sessionStorage) window.sessionStorage.setItem(seenKey, "1");

    window.phoenixAttribution.reportClick(impressionId);

    // Record it on the cart as well, which is what actually makes the click
    // billable. The report above only updates our own row; the cart attribute
    // is delivered to us on the order by Shopify, so it needs no session to
    // correlate and survives the shopper switching device.
    const productId = params.get("_bb_pid") || "";
    window.phoenixAttribution.recordClickOnCart(impressionId, productId);
  } catch (error) {
    // Never let attribution break a product page.
    if (window.phoenixLogger && window.phoenixLogger.warn) {
      window.phoenixLogger.warn("Phoenix: could not claim _bb_imp", error);
    }
  }
})();
