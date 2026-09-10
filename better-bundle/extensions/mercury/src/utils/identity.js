/**
 * The shopper identity that makes a checkout offer measurable.
 *
 * Checkout extensions run in their own sandbox with no access to the
 * storefront's localStorage, so they cannot see the visitor id Phoenix uses.
 * Without any identity two things silently break:
 *
 *   1. Holdout bucketing. `is_held_out` buckets on `md5(shop_id:identity)` and
 *      deliberately returns false when there is no identity — otherwise every
 *      anonymous shopper hashes to the same bucket, so either all of them are
 *      held out and the widget looks dead, or none are. The consequence is that
 *      checkout and thank-you offers were never bucketed at all: 21 impressions,
 *      0 in the experiment, so there is no control group and no way to say
 *      whether those offers caused anything.
 *
 *   2. Attribution. Impressions written with no session and no customer cannot
 *      be joined to a later order, so a click-through could be recorded and
 *      then never credited.
 *
 * The cart is the one thing both worlds can see. Phoenix writes `_bb_session`
 * there as a cart attribute; Shopify carries cart attributes into checkout and
 * onto the order. So reading it here gives this shopper the *same* identity
 * they had on the storefront — which matters more than merely having one: the
 * holdout is shop-level, so one identity means one bucket everywhere. Minting a
 * fresh id per surface instead would let the same person be treatment on the
 * product page and control at checkout, and that "control" shopper has already
 * seen recommendations, so they are not a counterfactual at all.
 */

const SESSION_ATTRIBUTE = "_bb_session";

/** Read `_bb_session` out of the cart attributes, if it is there. */
function readFromCart(shopify) {
  try {
    const attributes = shopify?.attributes?.value;
    if (!Array.isArray(attributes)) return null;
    const found = attributes.find((attr) => attr?.key === SESSION_ATTRIBUTE);
    return found?.value || null;
  } catch {
    return null;
  }
}

function newId() {
  try {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      return crypto.randomUUID();
    }
  } catch {
    // fall through
  }
  // Only reached on a runtime without randomUUID. Not cryptographic — this is
  // a bucketing key, not a secret.
  return `bb-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * The shopper's measurement id, minting and persisting one if the cart has none.
 *
 * Returns null when no id is available and none can be written — a shopper who
 * came straight to checkout on a store where writing attributes is not
 * permitted. That is the correct outcome rather than inventing a per-render id:
 * an id that changes on every render would rebucket the same shopper
 * repeatedly, which is worse for the experiment than not bucketing them, since
 * the backend at least flags an unbucketed impression with `bucketed: false`
 * and excludes it from the lift calculation.
 */
export async function resolveSessionId(shopify) {
  const existing = readFromCart(shopify);
  if (existing) return existing;

  // No id on the cart. Usually means the shopper never hit a product page with
  // the Phoenix block, or declined measurement consent there.
  const canWrite = Boolean(
    shopify?.instructions?.value?.attributes?.canUpdateAttributes,
  );
  if (!canWrite) return null;

  const minted = newId();
  try {
    const result = await shopify.applyAttributeChange({
      type: "updateAttribute",
      key: SESSION_ATTRIBUTE,
      value: minted,
    });
    if (result?.type !== "success") return null;
    // Persisted on the cart, so it reaches the thank-you page and the order
    // too — the same id for the whole journey.
    return minted;
  } catch {
    return null;
  }
}
