/**
 * Self-check for extensions/phoenix/assets/theme-adapt.js.
 *
 *   node scripts/theme-adapt.test.mjs
 *
 * Plain node against a hand-rolled DOM stub — no jsdom, no vitest config. The
 * asset is browser-global IIFE code, not a module, so it is read and evaluated
 * with the stub bound as its globals.
 *
 * The cases that matter most are the two at the end: a theme built from class
 * names this file has never heard of, and a theme with no recognisable classes
 * at all. Those are what stop the probe lists from being a Dawn/Savor lookup
 * table wearing a disguise.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import assert from 'node:assert/strict';
import vm from 'node:vm';

const SRC = join(dirname(fileURLToPath(import.meta.url)),
  '../extensions/phoenix/assets/theme-adapt.js');

/** Minimal element: the handful of DOM surface theme-adapt.js actually touches. */
function el(selectors, computed, opts = {}) {
  const node = {
    selectors,
    computed,
    offsetWidth: opts.width ?? 200,
    textContent: opts.text ?? 'Add to cart',
    children: opts.children ?? [],
    vars: {},
    style: { setProperty: (k, v) => { node.vars[k] = v; } },
    closest: (sel) => (opts.inWidget && sel === '.better-bundle-recommendations' ? {} : null),
  };
  return node;
}

function run({ body, nodes, themeAdapt = true }) {
  const widget = el(['.better-bundle-recommendations'], {}, { inWidget: true });
  const all = [widget, ...nodes];
  const document = {
    readyState: 'complete',
    body,
    addEventListener() {},
    querySelectorAll: (sel) => all.filter((n) => n.selectors.includes(sel)),
  };
  const ctx = { document, window: { themeAdapt }, getComputedStyle: (n) => n.computed };
  ctx.window.document = document;
  vm.createContext(ctx);
  vm.runInContext(readFileSync(SRC, 'utf8'), ctx);
  return Object.assign(widget.vars, { __report: ctx.window.bbThemeAdapt });
}

const LIGHT_BODY = el(['body'], {
  color: 'rgb(18, 18, 18)',
  backgroundColor: 'rgb(255, 255, 255)',
  fontFamily: 'Assistant, sans-serif',
});

const SOLID_BUTTON = {
  backgroundColor: 'rgb(212, 30, 30)',   // Savor-ish red
  backgroundImage: 'none',
  color: 'rgb(255, 255, 255)',
  borderRadius: '0px',                    // square, unlike our 6px default
  fontFamily: 'Savor, serif',
  fontWeight: '600',
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
};

const CART_FORM_BUTTON = 'form[action*="/cart/add"] [type="submit"]';

let n = 0;
const check = (name, fn) => { fn(); n++; console.log('  ok', name); };

// 1. The add-to-cart button is found through the Shopify form contract, not
//    through any theme's class name.
check('solid button adopted via /cart/add form', () => {
  const v = run({ body: LIGHT_BODY, nodes: [el([CART_FORM_BUTTON], SOLID_BUTTON)] });
  assert.equal(v['--bb-btn-bg'], 'rgb(212, 30, 30)');
  assert.equal(v['--bb-btn-radius'], '0px');
  assert.equal(v['--bb-btn-transform'], 'uppercase');
  assert.equal(v['--bb-btn-font'], 'Savor, serif');
});

// 2. Our own button is never the sample. Sniffing ourselves would latch the CSS
//    fallback in place on the first load and report it as the theme's colour.
check('never samples our own widget', () => {
  const ours = el([CART_FORM_BUTTON], { ...SOLID_BUTTON, backgroundColor: 'rgb(1, 2, 3)' },
    { inWidget: true });
  const theirs = el(['button'], SOLID_BUTTON);
  const v = run({ body: LIGHT_BODY, nodes: [ours, theirs] });
  assert.equal(v['--bb-btn-bg'], 'rgb(212, 30, 30)');
});

// 3. The broad `button` fallback must not settle on a hamburger or close icon.
check('icon buttons rejected in favour of a real CTA', () => {
  const icon = el(['button'], { ...SOLID_BUTTON, backgroundColor: 'rgba(0, 0, 0, 0)' },
    { width: 32, text: '' });
  const cta = el(['button'], SOLID_BUTTON);
  const v = run({ body: LIGHT_BODY, nodes: [icon, cta] });
  assert.equal(v['--bb-btn-bg'], 'rgb(212, 30, 30)', 'sampled the icon button');
});

// 4. `[class*="price"]` matches the wrapper before the span. The wrapper is not
//    where the typeface lives, so leaves win.
check('price wrapper skipped for the leaf that holds the money', () => {
  const leaf = el(['[class*="price" i]'], { fontFamily: 'Bodoni, serif', fontWeight: '700',
    letterSpacing: '0.04em', textTransform: 'none', fontStyle: 'normal' }, { text: '$24.00' });
  const wrapper = el(['[class*="price" i]'], { fontFamily: 'WRONG', fontWeight: '400',
    letterSpacing: 'normal', textTransform: 'none', fontStyle: 'normal' },
    { text: '$24.00', children: [leaf] });
  const v = run({ body: LIGHT_BODY, nodes: [wrapper, leaf] });
  assert.equal(v['--bb-price-font'], 'Bodoni, serif');
  assert.equal(v['--bb-price-weight'], '700');
});

// 5. Form controls are sampled apart from the button. Pill buttons with square
//    selects is a common pairing; borrowing one radius for both matches neither.
check('selects sampled separately from buttons', () => {
  const v = run({
    body: LIGHT_BODY,
    nodes: [
      el([CART_FORM_BUTTON], { ...SOLID_BUTTON, borderRadius: '999px' }),
      el(['select'], { borderRadius: '2px', borderTopWidth: '1px',
        borderTopColor: 'rgb(90, 90, 90)' }),
    ],
  });
  assert.equal(v['--bb-btn-radius'], '999px');
  assert.equal(v['--bb-input-radius'], '2px');
  assert.equal(v['--bb-input-border-color'], 'rgb(90, 90, 90)');
});

// 6. An outline theme button inverts into a fill rather than a ghost, so our
//    call-to-action still reads as the primary action inside the card.
check('outline button inverts to a solid fill', () => {
  const v = run({ body: LIGHT_BODY, nodes: [el([CART_FORM_BUTTON], { ...SOLID_BUTTON,
    backgroundColor: 'rgba(0, 0, 0, 0)', color: 'rgb(20, 60, 120)' })] });
  assert.equal(v['--bb-btn-bg'], 'rgb(20, 60, 120)');
  assert.equal(v['--bb-btn-fg'], 'rgb(255, 255, 255)');
});

// 7. A gradient button reports no background colour; the paint is in the image.
check('gradient button carries its background-image', () => {
  const v = run({ body: LIGHT_BODY, nodes: [el([CART_FORM_BUTTON], { ...SOLID_BUTTON,
    backgroundColor: 'transparent',
    backgroundImage: 'linear-gradient(90deg, rgb(255, 0, 0), rgb(0, 0, 255))' })] });
  assert.match(v['--bb-btn-bg-image'], /linear-gradient/);
});

// 8. Dark theme: borders and muted text derive from the text colour, so they
//    come out light instead of the near-invisible greys they were hardcoded to.
check('dark theme derives light borders', () => {
  const v = run({ body: el(['body'], { color: 'rgb(245, 245, 245)',
    backgroundColor: 'rgb(16, 16, 16)', fontFamily: 'serif' }), nodes: [] });
  assert.equal(v['--bb-border'], 'rgba(245,245,245,0.14)');
  assert.equal(v['--bb-surface'], 'rgb(16, 16, 16)');
  assert.equal(v['--bb-shimmer'], 'rgba(16,16,16,0.6)');
});

// 9. Toggle off publishes nothing, so the CSS falls through to block settings.
check('adapt off publishes no variables', () => {
  const v = run({ body: LIGHT_BODY, nodes: [el([CART_FORM_BUTTON], SOLID_BUTTON)],
    themeAdapt: false });
  assert.deepEqual(v, { __report: v.__report });
});

// 10. THE POINT OF THE TIERS. A theme whose class names this file has never
//     seen — no `.product-form__submit`, no `.card__heading`, no `.price-item`.
//     Everything is still found, through the platform contract, plain HTML, and
//     the English word in the class name.
check('unknown theme with unfamiliar class names still adapts', () => {
  const v = run({
    body: LIGHT_BODY,
    nodes: [
      el([CART_FORM_BUTTON], SOLID_BUTTON),                       // platform
      el(['select'], { borderRadius: '3px', borderTopWidth: '0px',
        borderTopColor: 'rgba(0,0,0,0)' }),                       // structural
      el(['h1'], { fontFamily: 'Chronicle, serif', fontWeight: '300',
        letterSpacing: 'normal', textTransform: 'none', fontStyle: 'normal' },
        { text: 'Hand-thrown Mug' }),                             // platform
      el(['[class*="price" i]'], { fontFamily: 'Chronicle, serif', fontWeight: '500',
        letterSpacing: 'normal', textTransform: 'none', fontStyle: 'normal' },
        { text: '£18.00' }),                                      // substring
      el(['[class*="card" i]'], { borderRadius: '14px', borderTopWidth: '2px',
        borderTopStyle: 'solid', borderTopColor: 'rgb(200, 200, 200)',
        boxShadow: 'none' }),                                     // substring
    ],
  });
  assert.equal(v['--bb-btn-bg'], 'rgb(212, 30, 30)');
  assert.equal(v['--bb-input-radius'], '3px');
  assert.equal(v['--bb-title-font'], 'Chronicle, serif');
  assert.equal(v['--bb-price-font'], 'Chronicle, serif');
  assert.equal(v['--bb-card-radius'], '14px');
  assert.equal(v['--bb-card-border'], '2px solid rgb(200, 200, 200)');
});

// 11. Nothing recognisable at all. Body-derived tokens still land, so the widget
//     is never worse off than the hardcoded values it replaced.
check('bare page still yields body-derived tokens', () => {
  const v = run({ body: LIGHT_BODY, nodes: [] });
  assert.equal(v['--bb-text'], 'rgb(18, 18, 18)');
  assert.equal(v['--bb-surface'], 'rgb(255, 255, 255)');
  assert.ok(!('--bb-btn-bg' in v), 'should leave the button to its CSS fallback');
});

// 12. The telemetry payload: what matched, per role, plus the theme Shopify
//     names for us. This is the only way to learn which real themes the probe
//     lists fail on, so its shape is worth pinning down.
check('publishes a diagnostic report for the request to carry', () => {
  const v = run({
    body: LIGHT_BODY,
    nodes: [el([CART_FORM_BUTTON], SOLID_BUTTON), el(['select'], { borderRadius: '4px',
      borderTopWidth: '0px', borderTopColor: 'rgba(0,0,0,0)' })],
  });
  const r = v.__report;
  assert.equal(r.enabled, true);
  assert.equal(r.button, CART_FORM_BUTTON, 'should name the selector that matched');
  assert.equal(r.button_fill, 'solid');
  assert.equal(r.input, 'select');
  // A miss is reported as a miss rather than omitted — "we looked and found
  // nothing" and "we never looked" are different findings.
  assert.equal(r.price, 'none');
  assert.equal(r.card, 'none');
});

// 13. Switched off still reports, so we can see how many merchants opt out
//     rather than inferring it from silence.
check('reports even when adaptation is off', () => {
  const v = run({ body: LIGHT_BODY, nodes: [el([CART_FORM_BUTTON], SOLID_BUTTON)],
    themeAdapt: false });
  assert.equal(v.__report.enabled, false);
  assert.ok(!('button' in v.__report), 'nothing probed when off');
});

console.log(`theme-adapt: ${n}/${n} ok`);
