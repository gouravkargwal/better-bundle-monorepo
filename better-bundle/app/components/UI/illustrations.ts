import { brand } from "./design.tokens";

/**
 * Empty-state illustrations, built on one motif: two products that belong
 * together.
 *
 * The motif is the point. Generic SaaS decoration — sparkles, blobs, gradient
 * mesh — is forgettable and says nothing about what the app does. Two shapes
 * finding each other is literally the product, so it reads as considered rather
 * than applied, and it gives the five placement contexts a family resemblance.
 *
 * Inline SVG data URIs rather than files, because Polaris `EmptyState` takes a
 * URL string. No asset pipeline, no CDN, nothing to 404, and they carry the
 * brand colour from `design.tokens` instead of hardcoding it a second time.
 *
 * Every empty state in this app was previously `image=""` — Polaris builds
 * `EmptyState` around an illustration, so an empty string leaves a headline
 * floating in whitespace. That was the single largest cause of the UI feeling
 * bland.
 *
 * Deliberately flat, geometric and two-tone: it survives being scaled down,
 * needs no dark-mode variant, and cannot be mistaken for a broken image.
 */

const INDIGO = brand.indigoStart;
const PLUM = brand.indigoEnd;
const MUTED = "#C9CCCF";

function svg(body: string): string {
  return (
    "data:image/svg+xml;utf8," +
    encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 140" fill="none">${body}</svg>`,
    )
  );
}

/**
 * Nothing has been shown to a shopper yet: two products exist but nothing
 * connects them. The gap and the dashed line carry the meaning — the pieces
 * are there, the link is not.
 */
export const NOT_SERVING_YET = svg(`
  <rect x="26" y="46" width="48" height="48" rx="12" fill="${INDIGO}" opacity="0.16"/>
  <rect x="26" y="46" width="48" height="48" rx="12" stroke="${INDIGO}" stroke-width="2"/>
  <rect x="126" y="46" width="48" height="48" rx="12" fill="${PLUM}" opacity="0.12"/>
  <rect x="126" y="46" width="48" height="48" rx="12" stroke="${PLUM}" stroke-width="2"/>
  <path d="M82 70h36" stroke="${MUTED}" stroke-width="2.5" stroke-linecap="round" stroke-dasharray="5 7"/>
  <circle cx="100" cy="70" r="4" fill="${MUTED}"/>
`);

/**
 * Offers are being shown but none accepted yet: the two shapes are joined, the
 * spark hasn't happened. Same composition as above with the link closed, so the
 * two states read as a sequence rather than as unrelated pictures.
 */
export const NO_ACCEPTED_YET = svg(`
  <rect x="26" y="46" width="48" height="48" rx="12" fill="${INDIGO}" opacity="0.16"/>
  <rect x="26" y="46" width="48" height="48" rx="12" stroke="${INDIGO}" stroke-width="2"/>
  <rect x="126" y="46" width="48" height="48" rx="12" fill="${PLUM}" opacity="0.12"/>
  <rect x="126" y="46" width="48" height="48" rx="12" stroke="${PLUM}" stroke-width="2"/>
  <path d="M74 70h52" stroke="${INDIGO}" stroke-width="2.5" stroke-linecap="round"/>
  <circle cx="100" cy="70" r="9" fill="#fff" stroke="${INDIGO}" stroke-width="2"/>
  <path d="M96 70h8M100 66v8" stroke="${INDIGO}" stroke-width="2" stroke-linecap="round"/>
`);

/** Nothing matched a search or filter — a pair, with one half missing. */
export const NOTHING_FOUND = svg(`
  <rect x="52" y="42" width="52" height="52" rx="13" fill="${INDIGO}" opacity="0.14"/>
  <rect x="52" y="42" width="52" height="52" rx="13" stroke="${INDIGO}" stroke-width="2"/>
  <rect x="112" y="42" width="52" height="52" rx="13" stroke="${MUTED}" stroke-width="2" stroke-dasharray="6 6"/>
  <circle cx="138" cy="68" r="11" stroke="${MUTED}" stroke-width="2"/>
  <path d="M146 76l7 7" stroke="${MUTED}" stroke-width="2.5" stroke-linecap="round"/>
`);

/** Preview idle: a pair waiting to be looked at. */
export const PREVIEW_IDLE = svg(`
  <rect x="34" y="40" width="46" height="46" rx="12" fill="${INDIGO}" opacity="0.16"/>
  <rect x="34" y="40" width="46" height="46" rx="12" stroke="${INDIGO}" stroke-width="2"/>
  <rect x="120" y="40" width="46" height="46" rx="12" fill="${PLUM}" opacity="0.12"/>
  <rect x="120" y="40" width="46" height="46" rx="12" stroke="${PLUM}" stroke-width="2"/>
  <path d="M80 63h40" stroke="${INDIGO}" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M70 106c10-13 20-13 30 0 10 13 20 13 30 0" stroke="${PLUM}" stroke-width="2.5" stroke-linecap="round"/>
`);
