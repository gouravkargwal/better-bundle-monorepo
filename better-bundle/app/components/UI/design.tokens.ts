// Brand colour, and nothing else.
//
// This file used to carry a parallel design system — `surfaces` (five
// background/border hex pairs), `radii`, `shadows` — duplicating tokens Polaris
// 12 already ships. Maintaining two systems meant every status had two possible
// greens and the app drifted from the admin whenever Shopify retuned its own.
//
// All of that is gone: backgrounds are `Box background="bg-surface-*"`, radii
// are `borderRadius`, status colour is `Badge tone`, and text colour is
// `Text tone`. What remains is the one thing Polaris genuinely has no token for
// — our own brand colour — kept solely for the empty-state illustrations, the
// one place a non-Polaris colour is appropriate.
export const brand = {
  indigoStart: "#667eea",
  indigoEnd: "#764ba2",
};
