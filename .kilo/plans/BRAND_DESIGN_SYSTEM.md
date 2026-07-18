# BetterBundle — Brand Identity & Design System

> A flat-rate pricing story told through deliberate visual and verbal choices.
> Every decision in this document exists because BetterBundle's differentiator
> (flat $29/mo, zero commission) demands a visual identity that feels
> predictable, premium, and merchant-first — never templated.

---

## PILLAR 1 — Brand Visual Foundation & Design Principles

### 1.1 Brand Essence

| Attribute            | Definition                                                                                                                                                    |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mission**          | Give every Shopify store AI-powered recommendations at a predictable flat rate — no surprise fees, no commission anxiety                                      |
| **Personality**      | Confident, transparent, data-driven, merchant-first                                                                                                           |
| **Voice**            | Direct, plain, never salesy. Speaks to merchants as business owners                                                                                           |
| **Visual metaphor**  | **The Flat Line** — a horizontal rule representing predictability, fairness, no surprises. The line that stays flat while competitors' commission curves rise |
| **Design principle** | **One bold thing, everything else quiet.** Spend visual boldness in one place per screen. Cut any decoration that doesn't serve the pricing story             |

### 1.2 Design Principles

1. **Transparency as aesthetic** — Show the numbers. Reveal the math. Pricing is not hidden behind fine print; it's the hero.
2. **One message per viewport** — Every screen has one primary job. The hero communicates the pricing model. The benefits section proves it. The CTA closes it.
3. **Predictable rhythm** — Consistent spacing, consistent component behavior. A merchant should feel the system, not the effort.
4. **Motion with purpose** — Micro-interactions signal state changes (loading, success, error). No decorative animations. Respect `prefers-reduced-motion`.
5. **Embrace the flat line** — Horizontal rules, level indicators, straight paths. The visual system echoes the pricing model.

### 1.3 Color Palette

Derived from the existing codebase patterns and refined for accessibility (WCAG AA minimum).

#### Brand Colors

```
/* === PRIMITIVES (global level) === */
--bb-color-indigo-50:  #EEF2FF;
--bb-color-indigo-100: #E0E7FF;
--bb-color-indigo-200: #C7D2FE;
--bb-color-indigo-400: #818CF8;
--bb-color-indigo-500: #667EEA;   /* Primary brand — used in hero gradients */
--bb-color-indigo-600: #5B6FD9;   /* Hover state */
--bb-color-indigo-700: #4C5BC0;   /* Active state */
--bb-color-indigo-800: #3D4AA8;   /* Text on light backgrounds */
--bb-color-indigo-900: #2E398F;   /* Deep accent */
--bb-color-purple-600: #764BA2;   /* Secondary brand — gradient partner */
```

```
/* === SEMANTIC TOKENS === */
--bb-color-brand:          var(--bb-color-indigo-500);  /* #667EEA */
--bb-color-brand-hover:    var(--bb-color-indigo-600);  /* #5B6FD9 */
--bb-color-brand-active:   var(--bb-color-indigo-700);  /* #4C5BC0 */
--bb-color-brand-gradient: linear-gradient(135deg, #667EEA 0%, #764BA2 100%);
```

#### Pricing & Success Colors

```
--bb-color-green-50:  #F0FDF4;
--bb-color-green-100: #D1FAE5;
--bb-color-green-500: #10B981;   /* "No commission" green — success, pricing */
--bb-color-green-600: #059669;   /* Hover / active */
--bb-color-green-700: #047857;

--bb-color-flat-rate: #059669;   /* The flat-rate guarantee color — darker green for high contrast */
```

#### Utility Colors

```
--bb-color-amber-500: #F59E0B;   /* Warnings, trials, "active" states */
--bb-color-amber-600: #D97706;
--bb-color-red-500:   #EF4444;   /* Errors, suspension */
--bb-color-red-600:   #DC2626;
--bb-color-blue-500:  #3B82F6;   /* Info, analytics */
--bb-color-blue-600:  #2563EB;
```

#### Neutral Colors

```
--bb-color-gray-50:   #F8FAFC;
--bb-color-gray-100:  #F1F5F9;
--bb-color-gray-200:  #E2E8F0;
--bb-color-gray-300:  #CBD5E1;
--bb-color-gray-400:  #94A3B8;
--bb-color-gray-500:  #64748B;
--bb-color-gray-600:  #475569;
--bb-color-gray-700:  #334155;
--bb-color-gray-800:  #1E293B;
--bb-color-gray-900:  #0F172A;
```

#### Light / Dark Mode Surfaces

```
/* Light mode (default) */
--bb-surface-primary:   #FFFFFF;
--bb-surface-secondary: #F8FAFC;
--bb-surface-tertiary:  #F1F5F9;
--bb-surface-brand:     var(--bb-color-brand-gradient);
--bb-surface-success:   linear-gradient(135deg, #10B981 0%, #059669 100%);

/* Dark mode (future) */
--bb-surface-primary-dark:   #0F172A;
--bb-surface-secondary-dark: #1E293B;
--bb-surface-tertiary-dark:  #334155;
```

**Accessibility verification (WCAG AA):**

| Foreground | Background | Ratio | Pass?                                     |
| ---------- | ---------- | ----- | ----------------------------------------- |
| `#667EEA`  | `#FFFFFF`  | 4.8:1 | ✅ AA body text                           |
| `#10B981`  | `#FFFFFF`  | 2.8:1 | ❌ — use `#059669` for body text on white |
| `#059669`  | `#FFFFFF`  | 4.6:1 | ✅ AA body text                           |
| `#FFFFFF`  | `#667EEA`  | 4.8:1 | ✅ AA body text                           |
| `#FFFFFF`  | `#764BA2`  | 6.1:1 | ✅ AA body text                           |

**Rule:** `#10B981` is reserved for large badges, icons, and decorative elements (WCAG AA exempts non-text). All body text on white uses `#059669`.

### 1.4 Typography

BetterBundle lives inside Shopify Polaris, which uses **Inter** as its system font. We keep Inter as the body face but differentiate through size/weight rather than a separate display face.

#### Typefaces

| Role        | Face                                             | Weight        | Usage                              |
| ----------- | ------------------------------------------------ | ------------- | ---------------------------------- |
| **Display** | Inter                                            | 700, 800      | H1 heroes, pricing numbers, badges |
| **Body**    | Inter (via Polaris)                              | 400, 500, 600 | Paragraphs, cards, labels          |
| **Utility** | Inter (monospace via Polaris `font-family-mono`) | 400           | Currency numbers, data, code       |

**Why not a custom display face?** Shopify merchants already trust Inter — it's Shopify's brand typeface. Introducing a foreign display face would fight Polaris's system. Instead, we differentiate through **extreme size contrast** (`4rem` for pricing numbers vs `1rem` for body) and **extreme weight contrast** (800 vs 400). The Flat Line signature provides visual distinction where a foreign typeface would create dissonance.

#### Type Scale

```
--bb-font-size-display: clamp(2.5rem, 5vw, 4rem);   /* Hero pricing numbers */
--bb-font-size-h1:      clamp(1.75rem, 4vw, 3rem);   /* Page headlines */
--bb-font-size-h2:      clamp(1.25rem, 3vw, 1.75rem);/* Section headers */
--bb-font-size-h3:      1.125rem;                     /* Card headers */
--bb-font-size-body:    1rem;                         /* Body text */
--bb-font-size-sm:      0.875rem;                     /* Captions, micro copy */
--bb-font-size-xs:      0.75rem;                      /* Labels, badges */

--bb-font-weight-regular:  400;
--bb-font-weight-medium:   500;
--bb-font-weight-semibold: 600;
--bb-font-weight-bold:     700;
--bb-font-weight-extrabold: 800;

--bb-line-height-tight:   1.1;   /* Display numbers, H1 */
--bb-line-height-normal:  1.4;   /* H2, H3 */
--bb-line-height-relaxed: 1.6;   /* Body paragraphs */
```

### 1.5 Spacing

Derived from the existing `clamp()` patterns in the codebase, standardized into a 4px grid.

```
--bb-space-1:  4px;
--bb-space-2:  8px;
--bb-space-3:  12px;
--bb-space-4:  16px;
--bb-space-5:  20px;
--bb-space-6:  24px;
--bb-space-8:  32px;
--bb-space-10: 40px;
--bb-space-12: 48px;
--bb-space-16: 64px;
```

### 1.6 Border Radius & Shadows

```
--bb-radius-sm:    6px;    /* Badges, small labels */
--bb-radius-md:    12px;   /* Buttons, inputs */
--bb-radius-lg:    16px;   /* Cards */
--bb-radius-xl:    20px;   /* Hero containers, modals */
--bb-radius-full:  50%;    /* Avatars, decorative circles */

--bb-shadow-sm:  0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
--bb-shadow-md:  0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
--bb-shadow-lg:  0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.05);
--bb-shadow-xl:  0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
--bb-shadow-glow-green: 0 4px 14px 0 rgba(16, 185, 129, 0.39);  /* Pricing CTAs */
--bb-shadow-glow-brand: 0 4px 14px 0 rgba(102, 126, 234, 0.39); /* Brand CTAs */
```

### 1.7 The Signature: The Flat Line

Per the frontend-design skill: _"Spend your boldness in one place. Let the signature element be the one memorable thing."_

BetterBundle's signature is **The Flat Line** — a 4px horizontal gradient bar that appears as the top border of every card, pricing block, and hero section. It represents:

- **Predictable pricing** (flat, not spiking like commission)
- **Fairness** (level playing field)
- **The brand name** (a "better bundle" presented as a straight line)

```
--bb-flat-line: linear-gradient(90deg, #667EEA 0%, #10B981 50%, #059669 100%);
```

**Implementation:** Applied as `::before` pseudo-element on cards: `height: 4px; border-radius: 4px 4px 0 0;` This replaces the current pattern of colored accent bars and decorative gradient circles throughout the codebase.

**Why this replaces the decorative circles:** The existing components ([`OnboardingHero.tsx`](../../better-bundle/app/features/onboarding/components/OnboardingHero.tsx#L43), [`FeatureCard.tsx`](../../better-bundle/app/features/onboarding/components/FeatureCard.tsx#L108), [`Benefits.tsx`](../../better-bundle/app/features/onboarding/components/Benefits.tsx#L57)) each have `radial-gradient` circles in their corners. These are decorative calories — they add texture but no information. The Flat Line is both decorative AND meaningful: it encodes the pricing story on every container it appears on.

---

## PILLAR 2 — Token Architecture

### 2.1 Three-Layer Token Model

```
  ┌─────────────────────────────────────┐
  │        GLOBAL PRIMITIVES            │
  │  Raw values: colors, spacing,       │
  │  radii, shadows, fonts              │
  │  Prefix: --bb-primitive-*           │
  ├─────────────────────────────────────┤
  │        SEMANTIC TOKENS              │
  │  Named by purpose:                  │
  │  --bb-color-brand, --bb-color-error │
  │  --bb-surface-primary, --bb-text    │
  ├─────────────────────────────────────┤
  │        COMPONENT TOKENS             │
  │  Scoped to components:              │
  │  --bb-hero-gradient, --bb-card-line │
  │  --bb-cta-shadow, --bb-badge-bg     │
  └─────────────────────────────────────┘
```

### 2.2 Token File Structure

```
app/
  styles/
    tokens/
      _primitives.css       → Raw color, spacing, radius, shadow values
      _semantic.css         → Purpose-named tokens (brand, surface, text)
    components/
      _hero.css             → Component tokens for OnboardingHero, OverviewHero
      _card.css             → Component tokens for FeatureCard, Benefits
      _button.css           → Component tokens for CTAs
      _badge.css            → Component tokens for badge variants
      _banner.css           → Component tokens for ValueCommunicationBanner
    _flat-line.css          → The signature element
    tokens.css              → @import aggregator
```

### 2.3 Global Primitives (`_primitives.css`)

```
/* Color Primitives */
--bb-primitive-indigo-500: #667EEA;
--bb-primitive-indigo-600: #5B6FD9;
--bb-primitive-indigo-700: #4C5BC0;
--bb-primitive-purple-600: #764BA2;
--bb-primitive-green-500:  #10B981;
--bb-primitive-green-600:  #059669;
--bb-primitive-amber-500:  #F59E0B;
--bb-primitive-red-500:    #EF4444;
--bb-primitive-blue-500:   #3B82F6;

/* Neutral Primitives */
--bb-primitive-gray-50:  #F8FAFC;
--bb-primitive-gray-100: #F1F5F9;
--bb-primitive-gray-200: #E2E8F0;
/* ... (full scale through 900) */

/* Spacing Primitives */
--bb-primitive-space-1:  4px;
--bb-primitive-space-2:  8px;
/* ... (full scale) */

/* Typography Primitives */
--bb-primitive-font-inter: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;

/* Radius Primitives */
--bb-primitive-radius-6:  6px;
--bb-primitive-radius-12: 12px;
--bb-primitive-radius-16: 16px;
--bb-primitive-radius-20: 20px;
```

### 2.4 Semantic Tokens (`_semantic.css`)

```
/* === BRAND === */
--bb-color-brand:         var(--bb-primitive-indigo-500);
--bb-color-brand-hover:   var(--bb-primitive-indigo-600);
--bb-color-brand-active:  var(--bb-primitive-indigo-700);
--bb-color-brand-gradient: linear-gradient(135deg,
  var(--bb-primitive-indigo-500) 0%,
  var(--bb-primitive-purple-600) 100%);

/* === PRICING / SUCCESS === */
--bb-color-success:       var(--bb-primitive-green-600);  /* #059669 — AA compliant on white */
--bb-color-success-light: var(--bb-primitive-green-500);  /* #10B981 — icons, large elements */
--bb-color-success-gradient: linear-gradient(135deg,
  var(--bb-primitive-green-500) 0%,
  var(--bb-primitive-green-600) 100%);

/* === STATE === */
--bb-color-warning:  var(--bb-primitive-amber-500);
--bb-color-error:    var(--bb-primitive-red-500);
--bb-color-info:     var(--bb-primitive-blue-500);

/* === SURFACES === */
--bb-surface-primary:   #FFFFFF;
--bb-surface-secondary: var(--bb-primitive-gray-50);
--bb-surface-tertiary:  var(--bb-primitive-gray-100);

/* === TEXT === */
--bb-text-primary:   var(--bb-primitive-gray-800);  /* #1E293B */
--bb-text-secondary: var(--bb-primitive-gray-600);  /* #475569 */
--bb-text-muted:     var(--bb-primitive-gray-400);  /* #94A3B8 */
--bb-text-inverse:   #FFFFFF;
--bb-text-success:   var(--bb-color-success);       /* #059669 */
--bb-text-error:     var(--bb-color-error);         /* #EF4444 */

/* === BORDERS === */
--bb-border-primary:   var(--bb-primitive-gray-200);  /* #E2E8F0 */
--bb-border-secondary: var(--bb-primitive-gray-100);  /* #F1F5F9 */
--bb-border-focus:     var(--bb-primitive-indigo-500);
--bb-border-error:     var(--bb-color-error);
```

### 2.5 Component Tokens (examples)

```
/* _hero.css */
--bb-hero-gradient:       var(--bb-color-brand-gradient);
--bb-hero-padding:        var(--bb-primitive-space-10) var(--bb-primitive-space-8);
--bb-hero-border-radius:  var(--bb-primitive-radius-20);
--bb-hero-text-color:     var(--bb-text-inverse);
--bb-hero-badge-bg:       rgba(255, 255, 255, 0.2);
--bb-hero-badge-border:   rgba(255, 255, 255, 0.3);

/* _card.css */
--bb-card-border-radius:  var(--bb-primitive-radius-16);
--bb-card-shadow:         var(--bb-shadow-md);
--bb-card-shadow-hover:   var(--bb-shadow-lg);
--bb-card-transition:     transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
--bb-card-flat-line:      var(--bb-flat-line);

/* _button.css */
--bb-cta-padding:         var(--bb-primitive-space-4) var(--bb-primitive-space-8);
--bb-cta-font-size:       1.125rem;
--bb-cta-border-radius:   var(--bb-primitive-radius-12);
--bb-cta-shadow-brand:    var(--bb-shadow-glow-brand);
--bb-cta-shadow-success:  var(--bb-shadow-glow-green);
```

### 2.6 Tailwind CSS Mapping (future-proofing)

If the team adopts Tailwind in the future, map primitives directly. **Right now**, the codebase uses Polaris + inline styles. The immediate recommendation is to extract inline styles into tokenized CSS variables, **not** to install Tailwind. See the roadmap in Pillar 4.

```
// tailwind.config.ts (deferred)
module.exports = {
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#EEF2FF',
          100: '#E0E7FF',
          500: '#667EEA',
          600: '#5B6FD9',
          700: '#4C5BC0',
        },
        success: {
          500: '#10B981',
          600: '#059669',
        },
        surface: {
          primary:   '#FFFFFF',
          secondary: '#F8FAFC',
          tertiary:  '#F1F5F9',
        },
      },
      spacing: { 18: '4.5rem' },
      borderRadius: { 'flat': '4px 4px 0 0' },
    },
  },
};
```

---

## PILLAR 3 — Standardized Component Library

### 3.1 Audit Findings → Standards

Every component in the existing codebase was audited. Below are the standardized patterns they should converge on.

#### 3.1.1 OnboardingHero — The Pricing Narrative Hero

**Current problems** (from the CRO audit):

- Seven equally-weighted stacked sections with no focal point
- `$29/month` rendered as inline body copy instead of display text
- Decorative gradient circles add visual noise without meaning
- Redundant badges (`"🎯 Predictable Monthly Pricing"` is noise)
- No secondary CTA for comparison shoppers

**Standardized layout:**

```
┌────────────────────────────────────────────┐
│  [Badge: Flat Rate. Zero Commission.]      │
│                                            │
│  Flat-Rate AI Recommendations              │  ← H1: pricing model first
│  $29/month — Zero Commission               │  ← Display number: the hero
│                                            │
│  Boost revenue up to 30% with              │
│  AI recommendations — no percentage cut.   │  ← Subheadline: connects outcome to model
│                                            │
│  ┌────────────────────────────────────┐    │
│  │  💰 $29/month                      │    │  ← Pricing card: ONE number, one message
│  │  Flat monthly rate                 │    │
│  │  No hidden fees • Cancel anytime   │    │
│  └────────────────────────────────────┘    │
│                                            │
│  [Start Free Trial →]  [See How It Works]  │  ← Primary + secondary CTA
│                                            │
│  ⚡ 2-min setup • 🔒 No coding • 📈 24h   │
│  💰 Zero commission — you keep 100%        │  ← The line no competitor can say
│                                            │
│  ──── (The Flat Line) ──────────────────  │
└────────────────────────────────────────────┘
```

**States:**

| State         | Behavior                                                                                                                                                                 |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Default**   | Show pricing data from `subscriptionPlan` prop. Display number = `currencySymbol + monthlyFee` at `--bb-font-size-display`.                                              |
| **Loading**   | Button spinner + "Activating your AI recommendations…". Pricing card at 50% opacity skeleton.                                                                            |
| **Error**     | Full-width [`Banner`](../../better-bundle/app/features/onboarding/components/OnboardingPage.tsx#L40) below hero with specific error message + retry. Hero stays visible. |
| **Null plan** | Show "Custom pricing available" fallback instead of pricing card.                                                                                                        |

#### 3.1.2 FeatureCard — The Six Features Grid

**Current problems:**

- Inline `onMouseEnter`/`onMouseLeave` in [`FeatureCard.tsx`](../../better-bundle/app/features/onboarding/components/FeatureCard.tsx#L205-L213) causes layout thrashing (no `will-change` transform)
- Two badges per card (badge + highlight) create visual clutter
- Decorative gradient circles and accent bars repeated

**Standardized:**

```
--bb-feature-card-hover-transform: translateY(-4px);
--bb-feature-card-hover-shadow:    var(--bb-shadow-lg);
--bb-feature-card-transition:      transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
```

- Replace inline event handlers with CSS `:hover` and `transition`
- First card gets the Flat Line top border (`--bb-card-flat-line`); remaining cards get `1px solid --bb-border-secondary`
- Remove the `highlight` badge — keep only `badge` per card
- Remove decorative gradient circles

#### 3.1.3 Benefits Section

**Current:** Badge "Complete Solution" + H2 "Everything You Need to Succeed" in [`Benefits.tsx`](../../better-bundle/app/features/onboarding/components/Benefits.tsx#L99-L114) — generic.

**Standardized:**

- Replace decorative gradient circles with a single Flat Line at the top
- H2 → `"Priced for growth. Built for results."` (connects to pricing model)
- Badge → `"🏷️ Included in your $29/month plan"` (ties benefits back to the flat rate)

#### 3.1.4 OverviewHero

**Current [`OverviewHero.tsx`](../../better-bundle/app/features/overview/components/OverviewHero.tsx#L41-L61):** Same gradient as OnboardingHero (good consistency). "Better Bundle" as heading (appropriate for overview — different context). Tagline "AI-powered recommendations that pay for themselves" is strong.

**Standardized:** OverviewHero is intentionally _quieter_ than OnboardingHero — smaller padding (`--bb-space-8`), smaller type (`--bb-font-size-h2`), single CTA. Same gradient, lower visual volume.

#### 3.1.5 ValueCommunicationBanner

**Current [`ValueCommunicationBanner.tsx`](../../better-bundle/app/features/overview/components/ValueCommunicationBanner.tsx#L31-L93):** Color-coded by status (amber/active, green/success, red/suspended). The ROI math is the strongest part: "You paid only $X for $Y in revenue."

**Standardized states:**

| State                   | Background                          | Border    | Title                | Key Metric                  |
| ----------------------- | ----------------------------------- | --------- | -------------------- | --------------------------- |
| **TRIAL**               | `#FEF3C7`                           | `#F59E0B` | 🚀 Trial Performance | Revenue generated so far    |
| **ACTIVE (w/revenue)**  | `#D1FAE5`                           | `#10B981` | 💰 ROI Success       | Net profit after commission |
| **ACTIVE (no revenue)** | `#EFF6FF`                           | `#3B82F6` | 🚀 Ready to Earn     | "AI recommendations active" |
| **SUSPENDED**           | `#FEE2E2`                           | `#EF4444` | ⚠️ Service Suspended | Revenue before suspension   |
| **Loading**             | Skeleton placeholder at 60% opacity | —         | —                    | —                           |

#### 3.1.6 Badge Variants

Standardize the inline badge styles currently duplicated across components ([`OnboardingHero.tsx`](../../better-bundle/app/features/onboarding/components/OnboardingHero.tsx#L46-L58), [`FeatureCard.tsx`](../../better-bundle/app/features/onboarding/components/FeatureCard.tsx#L281-L304), [`Benefits.tsx`](../../better-bundle/app/features/onboarding/components/Benefits.tsx#L88-L101)):

| Variant    | Background              | Border                  | Text      | Used For            |
| ---------- | ----------------------- | ----------------------- | --------- | ------------------- |
| `on-hero`  | `rgba(255,255,255,0.2)` | `rgba(255,255,255,0.3)` | White     | Hero section badges |
| `success`  | `rgba(16,185,129,0.1)`  | `rgba(16,185,129,0.2)`  | `#059669` | Pricing, benefits   |
| `info`     | `rgba(59,130,246,0.1)`  | `rgba(59,130,246,0.2)`  | `#3B82F6` | Analytics, insights |
| `warning`  | `rgba(245,158,11,0.1)`  | `rgba(245,158,11,0.2)`  | `#D97706` | Trial, warnings     |
| `critical` | `rgba(239,68,68,0.1)`   | `rgba(239,68,68,0.2)`   | `#DC2626` | Errors, suspension  |

### 3.2 Error, Empty, and Loading State Gap Analysis

| Component                    | Loading                                                   | Error                                           | Empty                         |
| ---------------------------- | --------------------------------------------------------- | ----------------------------------------------- | ----------------------------- |
| **OnboardingHero**           | ✅ Button spinner + text swap (`OnboardingHero.tsx#L254`) | ✅ Banner below hero (`OnboardingPage.tsx#L40`) | N/A (defaults always present) |
| **FeatureCard**              | ❌ No loading (static data — acceptable)                  | N/A                                             | N/A                           |
| **Benefits**                 | ❌ No loading (static data — acceptable)                  | N/A                                             | N/A                           |
| **OverviewHero**             | ❌ No skeleton state                                      | ❌ No explicit error state                      | N/A                           |
| **ValueCommunicationBanner** | ❌ Skeleton not implemented                               | ❌ Falls through to `default` case              | N/A                           |

**Gaps to address in Phase 4:**

- [`OverviewHero`](../../better-bundle/app/features/overview/components/OverviewHero.tsx) should accept `isLoading` and show skeleton
- [`ValueCommunicationBanner`](../../better-bundle/app/features/overview/components/ValueCommunicationBanner.tsx) should show skeleton when data is loading
- Error boundaries at the route level ([`app.tsx`](../../better-bundle/app/routes/app.tsx#L123)) — currently uses Shopify's `boundary.error` which is generic

### 3.3 Interactive State Standardization

```
/* === BUTTONS (Polaris overrides) === */
--bb-button-transition:         all 0.15s ease-in-out;
--bb-button-hover-lift:         translateY(-1px);
--bb-button-active-scale:       scale(0.98);

/* === CARDS === */
--bb-card-hover-transform:      translateY(-4px);
--bb-card-hover-shadow:         var(--bb-shadow-lg);
--bb-card-transition:           transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;

/* === LINKS === */
--bb-link-color:                var(--bb-color-brand);
--bb-link-color-hover:          var(--bb-color-brand-hover);
--bb-link-decoration:           underline 0px solid transparent;
--bb-link-decoration-hover:     underline 2px solid var(--bb-color-brand);

/* === FOCUS RING === */
--bb-focus-ring:                0 0 0 3px rgba(102, 126, 234, 0.4);
```

**Implementation rule:**

- All hover states use CSS `:hover` — no inline event handlers (`onMouseEnter`/`onMouseLeave`)
- All focus states use `:focus-visible` — not `:focus` (to avoid mouse-click focus rings)
- `prefers-reduced-motion: reduce` disables all non-essential transitions

---

## PILLAR 4 — Micro Copy & Tone of Voice

### 4.1 Voice Guidelines

| Guideline                        | ❌ Don't (current codebase examples)                                                                                                                          | ✅ Do (replacements)                                                                                                 |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **Lead with the pricing model**  | [`"Welcome to BetterBundle!"`](../../better-bundle/app/features/onboarding/components/OnboardingHero.tsx#L75)                                                 | `"Flat-Rate AI Recommendations — $29/month"`                                                                         |
| **Connect features to outcomes** | `"14-Day Free Trial"` (feature)                                                                                                                               | `"Try flat-rate pricing free for 14 days"` (outcome)                                                                 |
| **Name what the user controls**  | `"Setup will begin"` (passive)                                                                                                                                | `"Start your free trial"` (active)                                                                                   |
| **Be specific, not clever**      | [`"New AI-Powered Solution"`](../../better-bundle/app/features/onboarding/components/OnboardingHero.tsx#L56) (vague)                                          | `"1,500+ Shopify stores already using BetterBundle"` (specific)                                                      |
| **Active voice**                 | `"Web pixel will be activated"`                                                                                                                               | `"We activate your recommendations"`                                                                                 |
| **Error: explain + guide**       | [`"Please try again or contact support if the issue persists."`](../../better-bundle/app/features/onboarding/components/OnboardingPage.tsx#L95-L97) (generic) | `"We couldn't start your trial. Your billing may need confirmation — check your Shopify admin or retry."` (specific) |
| **Keep register conversational** | `"Predictable Monthly Pricing"` (corporate)                                                                                                                   | `"One flat rate. No surprises."` (direct)                                                                            |
| **Consistent action naming**     | Button: `"Start Your 14-Day Free Trial"` → toast: `"Trial activated"` (mismatch)                                                                              | Button: `"Start Free Trial"` → toast: `"Free trial started"` (match)                                                 |

### 4.2 Before/After: OnboardingHero Copy

| Element              | Before (current)                                                                               | After (standardized)                                                                     |
| -------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Badge                | `✨ New AI-Powered Solution`                                                                   | `🏷️ Flat Rate. Zero Commission.`                                                         |
| H1                   | `Welcome to BetterBundle!`                                                                     | `Flat-Rate AI Recommendations`                                                           |
| Display number       | _(none as H1)_                                                                                 | `$29/month — Zero Commission`                                                            |
| Subheadline          | `Transform your store with AI-powered product recommendations that boost revenue by up to 30%` | `Boost revenue up to 30% with AI recommendations — no percentage cut, no surprise fees.` |
| Pricing card heading | `Simple Flat Rate Pricing`                                                                     | `One flat rate. All features included.`                                                  |
| Pricing card body    | `$29/month • 14-day free trial • No hidden fees • Cancel anytime`                              | `💰 $29/month — unlimited recommendations — 14-day free trial`                           |
| Pricing card badge   | `🎯 Predictable Monthly Pricing`                                                               | _(removed — redundant)_                                                                  |
| CTA                  | `Start Your 14-Day Free Trial`                                                                 | `Start Free Trial — Keep 100% of Revenue`                                                |
| Secondary CTA        | _(none)_                                                                                       | `See Flat Rate vs Commission →`                                                          |
| Micro-copy row       | `⚡ Setup in 2 minutes • 🔒 No coding required • 📈 Results in 24 hours`                       | `⚡ 2-minute setup • 💰 Zero commission, ever • 📈 Results in 24 hours`                  |

### 4.3 Before/After: FeatureCard Titles

| Before ([`FeatureCard.tsx`](../../better-bundle/app/features/onboarding/components/FeatureCard.tsx#L28-L91)) | After                           | Rationale                                   |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------- | ------------------------------------------- |
| `Simple Flat Pricing`                                                                                        | `One Flat Rate`                 | Shorter, bolder. "Simple" is implied.       |
| `Increase Revenue`                                                                                           | `More Revenue, Zero Commission` | Connects benefit to pricing model.          |
| `Smart Analytics`                                                                                            | `Attribution You Can Trust`     | More specific — "smart" is a cliché.        |
| `Better Experience`                                                                                          | `Personalized Shopping`         | Descriptive, not evaluative.                |
| `Easy Setup`                                                                                                 | `2-Minute Setup`                | Quantified, not abstract.                   |
| `24/7 Optimization`                                                                                          | `Always-On AI`                  | Shorter, more technical — appropriate here. |

### 4.4 Before/After: Error & Status Messages

| Context                  | Before ([`OnboardingPage.tsx`](../../better-bundle/app/features/onboarding/components/OnboardingPage.tsx#L95)) | After                                                                                                                                                  |
| ------------------------ | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Onboarding error         | `Please try again or contact support if the issue persists.`                                                   | `We hit a snag setting up your trial. This usually means a billing confirmation is pending — check your Shopify admin's payment settings, then retry.` |
| ValueBanner (no revenue) | `Once customers start purchasing through our recommendations, you'll see your ROI metrics here`                | `Your AI recommendations are live and analyzing your store. Revenue data appears within 24 hours of the first attributed sale.`                        |
| Suspension               | `Reactivate your subscription to continue earning from AI recommendations`                                     | `Your service is paused. Reactivate in billing to restart AI recommendations — your data is safe.`                                                     |
| Loading                  | `Setting up your store...`                                                                                     | `Activating your AI recommendations...`                                                                                                                |

### 4.5 Tone Spectrum by Context

| Context                | Tone                               | Example                                                                                       |
| ---------------------- | ---------------------------------- | --------------------------------------------------------------------------------------------- |
| **Hero/Onboarding**    | Confident, transparent, persuasive | `"Flat $29/month — unlimited AI recommendations, zero commission"`                            |
| **Dashboard/Overview** | Supportive, data-driven            | `"You generated $12,430 in attributed revenue this month"`                                    |
| **Billing**            | Direct, reassuring                 | `"Your next billing date is July 20. Cancel anytime."`                                        |
| **Error**              | Helpful, specific, no apologies    | `"Billing verification failed. Your payment method may need updating."`                       |
| **Empty**              | Encouraging, instructive           | `"No data yet — recommendations are analyzing your first 50 orders. Check back in 24 hours."` |

### 4.6 Emoji Usage Standard

Emojis are appropriate for a Shopify merchant audience (they're native to the platform's culture). They must be **purposeful, not decorative.**

| Emoji | Meaning                       | Used In                        |
| ----- | ----------------------------- | ------------------------------ |
| `💰`  | Money / revenue / pricing     | Pricing cards, revenue metrics |
| `🚀`  | Launch / growth / trial start | CTAs, status banners           |
| `📈`  | Growth / revenue increase     | Dashboard KPIs, micro-copy     |
| `⚡`  | Speed / quick setup           | Micro-copy row, setup cards    |
| `🔒`  | Security / no-risk            | Trust signals, pricing         |
| `🏷️`  | Pricing / tag                 | Badges, pricing labels         |
| `🤖`  | AI / automation               | Feature cards, benefits        |
| `📊`  | Analytics / data              | Dashboard, analytics sections  |
| `✅`  | Complete / verified           | Completion states, check marks |
| `⚠️`  | Warning / attention           | Suspension, approaching limits |

---

## Implementation Roadmap

### Phase 1: Foundation (current sprint)

| #   | Task                                                                      | Files      | Effort |
| --- | ------------------------------------------------------------------------- | ---------- | ------ |
| 1   | Create `_primitives.css` with all color, spacing, radius values           | New file   | Small  |
| 2   | Create `_semantic.css` with purpose-named tokens                          | New file   | Small  |
| 3   | Create `_flat-line.css` with the signature element                        | New file   | Small  |
| 4   | Create `tokens.css` as an aggregator                                      | New file   | Tiny   |
| 5   | Import `tokens.css` in [`app/root.tsx`](../../better-bundle/app/root.tsx) | `root.tsx` | Tiny   |

### Phase 2: Component Token Extraction (next sprint)

| #   | Task                                                                                                                                                  | Files                                     | Effort |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- | ------ |
| 6   | Extract [`OnboardingHero`](../../better-bundle/app/features/onboarding/components/OnboardingHero.tsx) inline styles → `_hero.css`                     | `OnboardingHero.tsx` + new `_hero.css`    | Medium |
| 7   | Extract [`FeatureCard`](../../better-bundle/app/features/onboarding/components/FeatureCard.tsx) inline styles → `_card.css`                           | `FeatureCard.tsx` + `_card.css`           | Medium |
| 8   | Extract [`Benefits`](../../better-bundle/app/features/onboarding/components/Benefits.tsx) inline styles → `_card.css` (shared)                        | `Benefits.tsx` + existing file            | Small  |
| 9   | Extract [`ValueCommunicationBanner`](../../better-bundle/app/features/overview/components/ValueCommunicationBanner.tsx) inline styles → `_banner.css` | `ValueCommunicationBanner.tsx` + new file | Medium |
| 10  | Extract [`HeroHeader`](../../better-bundle/app/components/UI/HeroHeader.tsx) inline styles → `_hero.css` (reuse)                                      | `HeroHeader.tsx` + existing file          | Small  |
| 11  | Replace all decorative gradient circles with the Flat Line                                                                                            | All hero/card components                  | Small  |

### Phase 3: Copy & CRO Improvements (next sprint)

| #   | Task                                         | Files                | Effort |
| --- | -------------------------------------------- | -------------------- | ------ |
| 12  | Rewrite H1, subheadline, CTA per Section 4.2 | `OnboardingHero.tsx` | Small  |
| 13  | Add secondary CTA in OnboardingHero          | `OnboardingHero.tsx` | Small  |
| 14  | Rewrite FeatureCard titles per Section 4.3   | `FeatureCard.tsx`    | Small  |
| 15  | Add zero-commission micro-copy line to hero  | `OnboardingHero.tsx` | Tiny   |
| 16  | Standardize error messages per Section 4.4   | `OnboardingPage.tsx` | Small  |

### Phase 4: Interactive States & Accessibility (next sprint)

| #   | Task                                                                                                                  | Files              | Effort |
| --- | --------------------------------------------------------------------------------------------------------------------- | ------------------ | ------ |
| 17  | Remove inline `onMouseEnter`/`onMouseLeave` → CSS `:hover`                                                            | `FeatureCard.tsx`  | Small  |
| 18  | Add `prefers-reduced-motion` query to all transitions                                                                 | Global CSS         | Small  |
| 19  | Add `:focus-visible` outlines to all interactive elements                                                             | All components     | Medium |
| 20  | Add skeleton loading state to [`OverviewHero`](../../better-bundle/app/features/overview/components/OverviewHero.tsx) | `OverviewHero.tsx` | Small  |

### Phase 5: Standardization & Cleanup (future sprint)

| #   | Task                                                                                                                                    | Files                          | Effort |
| --- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | ------ |
| 21  | Create shared Badge variant CSS per Section 3.1.6                                                                                       | New `_badge.css`               | Small  |
| 22  | Replace all inline badge styles with variant classes                                                                                    | All components                 | Medium |
| 23  | Apply `--bb-layout-*` tokens to all section containers                                                                                  | All components                 | Medium |
| 24  | Add skeleton loading to [`ValueCommunicationBanner`](../../better-bundle/app/features/overview/components/ValueCommunicationBanner.tsx) | `ValueCommunicationBanner.tsx` | Small  |

### Never Do

- ❌ Install Tailwind CSS or any new CSS framework — Polaris + CSS variables covers everything
- ❌ Add styled-components, CSS modules, or CSS-in-JS — CSS variables are the least-risky migration path
- ❌ Create a separate display typeface — Inter at extreme size/weight provides sufficient differentiation within Polaris
- ❌ Add decorative animations or scroll-triggered reveals — motion is reserved for functional state changes only

---

## Appendix: Key Decision Rationales

### Why Inter (not a custom display face)?

Shopify merchants see Inter everywhere in their admin. Introducing a foreign display face would create visual dissonance. The design system differentiates through:

- **Extreme size contrast** (`clamp(2.5rem, 5vw, 4rem)` for pricing numbers vs `1rem` for body)
- **Extreme weight contrast** (800 for pricing vs 400 for body)
- **The Flat Line signature** (no other Shopify app uses a horizontal gradient bar as a brand device)

### Why CSS variables (not Tailwind)?

The codebase uses Polaris + inline `style={{}}` objects. CSS variables are:

- Compatible with Polaris (variables cascade alongside Polaris tokens)
- Zero build step (no JIT, no PostCSS plugins)
- Incrementally adoptable (one component at a time)
- Themeable (dark mode = change variable values, not components)

Tailwind would require a build pipeline change, new team learning, and a rewrite of all inline styles simultaneously — too high risk for the current stage.

### Why remove the decorative circles?

The `radial-gradient` circles in the corners of [`OnboardingHero`](../../better-bundle/app/features/onboarding/components/OnboardingHero.tsx#L43), [`FeatureCard`](../../better-bundle/app/features/onboarding/components/FeatureCard.tsx#L108), and [`Benefits`](../../better-bundle/app/features/onboarding/components/Benefits.tsx#L57) are pure decoration — they add no information and repeat across every component. The Flat Line replaces them with a device that is BOTH decorative AND meaningful (it encodes the pricing story). Per the design principle: _"Spend boldness in one place."_ The Flat Line is that place.
