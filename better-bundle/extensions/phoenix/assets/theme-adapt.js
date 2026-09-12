/**
 * Reads the host theme's own rendered styles and republishes them as CSS
 * variables on our block.
 *
 * Why sniffing and not theme CSS variables: a theme app extension renders
 * inside the merchant's stylesheet, but there is no shared vocabulary for what
 * that stylesheet is called. `rgb(var(--color-button, 18 18 18))` — what this
 * replaces — is a Dawn token in Dawn's own space-separated-triplet format.
 * Savor does not define it, so every Savor merchant got the literal fallback:
 * a black, 6px-rounded button on a store whose buttons are red and square.
 * Every theme names its tokens differently, so a lookup table would need a row
 * per theme on the store, forever.
 *
 * The rendered page already knows the answer. We ask a real theme button what
 * colour it is, and copy that.
 *
 * Precedence, highest first:
 *   1. an explicit merchant setting  (emitted as a literal by the Liquid, so
 *      it never consults these variables at all)
 *   2. the value sniffed here
 *   3. the hardcoded fallback in the CSS var's own default
 */
(function () {
  'use strict';

  var ROOT = '.better-bundle-recommendations';

  /* Which selector last matched. Written by probe(), read into the report
     below. A module-level slot is safe because probing is synchronous and one
     call cannot overlap another. */
  var lastSelector = null;

  /* What this run actually found, published for api.js to attach to the
     recommendations request it was already making. This is the honest answer to
     "do the probe lists cover the themes our merchants really use" — the lists
     are a heuristic, and without this we would be guessing about how well the
     heuristic does on the long tail of the theme store. */
  var report = {};

  /* ------------------------------------------------------------------ *
   * Finding something to measure.
   *
   * Each list runs most-reliable first, and the tiers are deliberate:
   *
   *   1. PLATFORM  — guaranteed by Shopify, not by the theme. Every storefront
   *      posts to `/cart/add`; every product page has one `h1`. A theme cannot
   *      opt out of these and still function, so they work on themes nobody
   *      has ever seen.
   *   2. STRUCTURAL — plain HTML. `select`, `textarea`, `input[type=text]`.
   *      Also theme-independent.
   *   3. SUBSTRING — `[class*="price" i]` rather than `.price-item--regular`.
   *      One selector covers `.ProductMeta__Price`, `.product-single__price`,
   *      `.price--large` and whatever the next theme invents, because themes
   *      converge on the English word even when they disagree on the format.
   *   4. NAMED — the handful of Dawn/OS2 class names, LAST, as a tie-breaker
   *      only. These are the ones that are genuinely Dawn-specific, and
   *      nothing depends on them.
   *
   * A miss is not a failure: with no match the variable stays unset and the
   * CSS falls through to a body-derived token, which is still read from the
   * live theme. The old code had no tier at all — it asserted Dawn's variable
   * name and shipped a black button when it was wrong.
   * ------------------------------------------------------------------ */

  // `form[action*="/cart/add"]` is the Shopify storefront contract for adding
  // to cart. Its submit control is the theme's primary button by definition —
  // no class name required.
  var BUTTON_PROBES = [
    'form[action*="/cart/add"] [type="submit"]',
    'form[action*="/cart/add"] button:not([type="button"])',
    'form[action*="/cart"] [type="submit"]',
    '[class*="add-to-cart" i]',
    '[class*="add_to_cart" i]',
    '[name="add"]',
    'button[class*="primary" i]',
    'a[class*="button" i]',
    '[class*="button" i]:not(input)',
    '[class*="btn" i]:not(input)',
    'button[type="submit"]',
    'button',
  ];

  // Already structural: a dropdown is a `select` on every theme ever written.
  var INPUT_PROBES = [
    'select',
    'input[type="text"]',
    'input[type="email"]',
    'input[type="search"]',
    'input[type="number"]',
    'input[type="tel"]',
    'textarea',
    '[class*="select" i]',
    '[class*="field__input" i]',
  ];

  // A theme almost never leaves its price in the body font — it is usually the
  // heading face, or a tabular/semibold cut, with its own tracking. Our price
  // inherits from body, so on a theme like that it was the one line in the card
  // set in the wrong typeface.
  var PRICE_PROBES = [
    '[class*="price" i]',
    '[class*="money" i]',
    '[data-price]',
    '[class*="Price"]',
  ];

  // On a product page the `h1` is the product title on every theme — the page
  // has exactly one top-level heading and that is what it is for.
  var TITLE_PROBES = [
    'h1',
    '[class*="product-title" i]',
    '[class*="product__title" i]',
    '[class*="card__heading" i]',
    '[class*="heading" i]',
    'h2',
  ];

  var CARD_PROBES = [
    '[class*="card__content" i]',
    '[class*="card-wrapper" i]',
    '[class*="product-card" i]',
    '[class*="card" i]',
    '[class*="grid__item" i]',
  ];

  /**
   * First element matching any selector that is neither part of our own widget
   * nor rejected by `validate`.
   *
   * Excluding our own widget is load-bearing: several of these selectors match
   * our cards too, and sampling ourselves would latch the CSS fallback in place
   * on the first load and then report it as the theme's own colour.
   */
  function probe(selectors, validate) {
    lastSelector = null;
    for (var i = 0; i < selectors.length; i++) {
      var found;
      try {
        found = document.querySelectorAll(selectors[i]);
      } catch (e) {
        // A selector a browser rejects must not take the rest of the list down
        // with it — the whole point of the list is that later entries cover
        // what earlier ones miss.
        continue;
      }
      for (var j = 0; j < found.length; j++) {
        var node = found[j];
        if (node.closest(ROOT)) continue;
        if (validate && !validate(node)) continue;
        lastSelector = selectors[i];
        return node;
      }
    }
    return null;
  }

  /* Validators. Broad selectors are what make this work on a theme nobody has
     seen, and they are also what lets a hamburger icon pose as the primary
     button or a `.price-wrapper` div pose as the price. Each role states what a
     plausible sample looks like, in properties every theme's DOM has. */

  /** Rendered width, or 0 when the element is not laid out. 0 means "cannot
   *  judge", never "too small" — rejecting on it would discard good samples on
   *  a theme that builds its cart form after load. */
  function width(node) {
    return node.offsetWidth || 0;
  }

  function text(node) {
    return (node.textContent || '').trim();
  }

  /** A primary button is wide enough to hold a word. Icon buttons, close
   *  crosses and quantity steppers are small and square; sampling one gives us
   *  a 32px transparent box and calls it the theme's call-to-action. */
  function isButtonish(node) {
    var w = width(node);
    if (w > 0 && w < 60) return false;
    var t = text(node);
    return t.length > 0 && t.length < 60;
  }

  /** The price is the element holding the money, not the div wrapping it.
   *  Requiring a leaf skips `.price` (a wrapper on most themes) and lands on
   *  the span inside it, which is where the typeface actually is. */
  function isPriceish(node) {
    if (node.children && node.children.length > 0) return false;
    var t = text(node);
    return t.length > 0 && t.length <= 30 && /\d/.test(t);
  }

  function isTitleish(node) {
    var t = text(node);
    return t.length > 0 && t.length < 200;
  }

  /** A product card is a layout box, not a badge or a swatch. */
  function isCardish(node) {
    var w = width(node);
    return w === 0 || w >= 120;
  }

  /** A colour we can actually use — not transparent, not unset. */
  function opaque(color) {
    if (!color) return false;
    if (color === 'transparent') return false;
    var parts = color.match(/[\d.]+/g);
    // rgba(…, 0) and rgba(0,0,0,0) are the browser's way of saying "nothing here".
    return !(parts && parts.length > 3 && parseFloat(parts[3]) < 0.05);
  }

  /** Same hue as `color`, at `alpha` — for borders and muted text derived from
   *  the theme's text colour, so a dark theme gets light borders for free. */
  function fade(color, alpha) {
    var parts = color && color.match(/[\d.]+/g);
    if (!parts || parts.length < 3) return null;
    return 'rgba(' + parts[0] + ',' + parts[1] + ',' + parts[2] + ',' + alpha + ')';
  }

  /** probe(), plus a note of which tier answered. The selector string IS the
   *  tier — `form[action*="/cart/add"] ...` is the platform contract, `select`
   *  is plain HTML, `[class*="price" i]` is the substring guess — so recording
   *  it verbatim is both the diagnosis and the evidence, with no tier labels to
   *  keep in step with the lists. */
  function find(role, selectors, validate) {
    var node = probe(selectors, validate);
    report[role] = lastSelector || 'none';
    return node;
  }

  /** Copy a theme element's typeface onto `prefix`-named variables. */
  function typography(el, role, selectors, prefix, validate) {
    var found = find(role, selectors, validate);
    if (!found) return;
    var c = getComputedStyle(found);
    set(el, prefix + '-font', c.fontFamily);
    set(el, prefix + '-weight', c.fontWeight);
    set(el, prefix + '-tracking', c.letterSpacing);
    set(el, prefix + '-transform', c.textTransform);
    set(el, prefix + '-style', c.fontStyle);
  }

  function set(el, name, value) {
    if (value) el.style.setProperty(name, value);
  }

  function adapt(el) {
    var body = getComputedStyle(document.body);
    var text = body.color;
    var surface = opaque(body.backgroundColor) ? body.backgroundColor : '#ffffff';

    // Surface and text first: everything else is derived from these, and they
    // are the two we can always read.
    set(el, '--bb-text', text);
    set(el, '--bb-text-muted', fade(text, 0.62));
    set(el, '--bb-surface', surface);
    set(el, '--bb-border', fade(text, 0.14));
    set(el, '--bb-border-strong', fade(text, 0.45));
    set(el, '--bb-surface-alt', fade(text, 0.04));
    set(el, '--bb-skeleton', fade(text, 0.08));
    // The skeleton shimmer used to be a hardcoded white sweep: invisible on a
    // light theme's grey bar, a glare on a dark one. Derived from the surface
    // it sweeps across, it reads correctly in both.
    set(el, '--bb-shimmer', fade(surface, 0.6));
    set(el, '--bb-font', body.fontFamily);

    var btn = find('button', BUTTON_PROBES, isButtonish);
    if (btn) {
      var b = getComputedStyle(btn);

      // Geometry and type always transfer — they are meaningful even on an
      // outline button, which is the case the colour branch below guards.
      set(el, '--bb-btn-radius', b.borderRadius);
      set(el, '--bb-btn-font', b.fontFamily);
      set(el, '--bb-btn-weight', b.fontWeight);
      set(el, '--bb-btn-transform', b.textTransform);
      set(el, '--bb-btn-tracking', b.letterSpacing);

      if (opaque(b.backgroundColor)) {
        report.button_fill = 'solid';
        set(el, '--bb-btn-bg', b.backgroundColor);
        set(el, '--bb-btn-fg', b.color);
      } else if (b.backgroundImage && b.backgroundImage !== 'none') {
        // Gradient buttons report a transparent backgroundColor. The paint is
        // all in the image, so carry that instead.
        report.button_fill = 'gradient';
        set(el, '--bb-btn-bg-image', b.backgroundImage);
        set(el, '--bb-btn-bg', 'transparent');
        set(el, '--bb-btn-fg', b.color);
      } else {
        // A genuinely outlined theme button. Inverting it into a solid fill
        // using its own text colour keeps our primary action looking primary,
        // which a ghost button in a recommendation carousel does not.
        // Inverted, so worth flagging: this is the one branch where we
        // change the theme's intent rather than copy it.
        report.button_fill = 'outline-inverted';
        set(el, '--bb-btn-bg', opaque(b.color) ? b.color : text);
        set(el, '--bb-btn-fg', surface);
      }
    }

    // Family, weight and tracking only — deliberately not font-size. A theme's
    // price element may be the 32px one on its product page; ours has to fit a
    // carousel card, so the size stays ours and only the typeface travels.
    typography(el, 'price', PRICE_PROBES, '--bb-price', isPriceish);
    typography(el, 'title', TITLE_PROBES, '--bb-title', isTitleish);

    var input = find('input', INPUT_PROBES);
    if (input) {
      var i = getComputedStyle(input);
      set(el, '--bb-input-radius', i.borderRadius);
      if (parseFloat(i.borderTopWidth) > 0 && opaque(i.borderTopColor)) {
        set(el, '--bb-input-border-width', i.borderTopWidth);
        set(el, '--bb-input-border-color', i.borderTopColor);
      }
    }

    var card = find('card', CARD_PROBES, isCardish);
    if (card) {
      var c = getComputedStyle(card);
      set(el, '--bb-card-radius', c.borderRadius);
      if (parseFloat(c.borderTopWidth) > 0 && opaque(c.borderTopColor)) {
        set(el, '--bb-card-border', c.borderTopWidth + ' ' + c.borderTopStyle + ' ' + c.borderTopColor);
      }
      if (c.boxShadow && c.boxShadow !== 'none') {
        set(el, '--bb-card-shadow', c.boxShadow);
      }
    }
  }

  function run() {
    report = { enabled: window.themeAdapt !== false };

    // `Shopify.theme` is injected by Shopify itself on every storefront, not by
    // the theme, so it is present even on the themes our probes handle worst —
    // which are exactly the ones we need named. `theme_store_id` identifies a
    // theme-store theme; it is absent on a custom or heavily forked one, and
    // that absence is itself worth knowing.
    var t = (window.Shopify && window.Shopify.theme) || {};
    report.theme_name = t.name || null;
    report.theme_store_id = t.theme_store_id || null;

    // The merchant can switch this off and drive everything from the block
    // settings instead. Leaving the variables unset is the whole mechanism:
    // each `var(--bb-…, fallback)` in the stylesheet then resolves to its
    // fallback, which is the merchant setting.
    if (report.enabled) {
      var blocks = document.querySelectorAll(ROOT);
      for (var i = 0; i < blocks.length; i++) adapt(blocks[i]);
    }

    // Read by api.js and attached to the recommendations request it was making
    // anyway — no extra round trip, no new endpoint, nothing on the critical
    // path. If api.js has already fired by now the report simply rides the next
    // page's request; this is a population-level signal, not a per-view one.
    window.bbThemeAdapt = report;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }

  // The theme customiser replaces our section's DOM without reloading the page,
  // so the element carrying the variables is thrown away and the merchant sees
  // the widget snap back to its fallbacks mid-edit.
  document.addEventListener('shopify:section:load', run);
})();
