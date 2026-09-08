/**
 * Visitor identity for holdout bucketing — consent-gated.
 *
 * The only thing this id does is keep a shopper in the same control/treatment
 * bucket across page loads. Without that stability an anonymous shopper flips
 * buckets between pages and the control group stops being a clean
 * counterfactual, which is the basis for what merchants are billed.
 *
 * It is nonetheless a persistent unique identifier whose purpose is
 * measurement, not delivering functionality the shopper asked for. So it is
 * gated on the merchant's own consent banner via Shopify's Customer Privacy
 * API, and never written when consent is absent or unknown.
 *
 * What happens without consent
 * ----------------------------
 * No id is created and none is sent. The backend then skips holdout bucketing
 * and serves recommendations to that shopper — they get the feature, they are
 * simply excluded from the lift calculation.
 *
 * Attribution mostly survives this. The cart-line stamp stores nothing on the
 * device and travels as order data, so an add from the widget is still credited
 * in full. Only the click-then-buy-later path is lost, because that is the one
 * that genuinely needs to recognise the same person days later.
 *
 * NOT legal advice. Consent rules vary by jurisdiction and the merchant is the
 * data controller here — this defaults to the conservative reading.
 */

const VISITOR_ID_KEY = "bb_visitor_id";

/**
 * Whether the shopper has allowed the kind of processing this id represents.
 *
 * Returns false when the API is unavailable or throws. Defaulting to "no"
 * means a misconfigured banner costs measurement data, not compliance.
 */
function measurementAllowed() {
  try {
    const privacy = window.Shopify && window.Shopify.customerPrivacy;
    if (!privacy) {
      // No privacy API on the page. Cannot establish consent, so assume none.
      return false;
    }
    // Analytics covers audience measurement; preferences covers storing a
    // choice about the shopper. Either is sufficient for a bucketing id.
    const analytics =
      typeof privacy.analyticsProcessingAllowed === "function"
        ? privacy.analyticsProcessingAllowed()
        : false;
    const preferences =
      typeof privacy.preferencesProcessingAllowed === "function"
        ? privacy.preferencesProcessingAllowed()
        : false;
    return Boolean(analytics || preferences);
  } catch (e) {
    return false;
  }
}

function newId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  // Older browsers: random is sufficient here. This id is a bucketing key, not
  // a security token.
  return `v-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

/**
 * The visitor id, or null when consent is absent.
 *
 * Reads an existing id even without consent only to remove it, so that a
 * shopper who withdraws consent stops being recognised.
 */
function getVisitorId() {
  let stored = null;
  try {
    stored = window.localStorage.getItem(VISITOR_ID_KEY);
  } catch (e) {
    // Private browsing or blocked storage. Nothing to do; treat as no id.
    return null;
  }

  if (!measurementAllowed()) {
    // Consent absent or withdrawn: drop any id we previously stored.
    if (stored) {
      try {
        window.localStorage.removeItem(VISITOR_ID_KEY);
      } catch (e) {
        /* nothing useful to do */
      }
    }
    return null;
  }

  if (stored) return stored;

  const created = newId();
  try {
    window.localStorage.setItem(VISITOR_ID_KEY, created);
  } catch (e) {
    // Could not persist. Returning it anyway would bucket this page load
    // differently from the next, which is worse than not bucketing at all.
    return null;
  }
  return created;
}

window.bbGetVisitorId = getVisitorId;
window.bbMeasurementAllowed = measurementAllowed;
