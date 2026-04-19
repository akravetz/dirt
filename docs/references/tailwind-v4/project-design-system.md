---
title: Porting the Dirt design system
concept: tailwind-v4
updated: 2026-04-19
source: debug/webapp.zip/colors_and_type.css
---

> Anchors agents porting the Dirt mockup tokens into `web-ui/src/styles.css`. The source of truth for the palette, fonts, and spacing scale is `debug/webapp.zip/colors_and_type.css` (mirrored in `raw/mockup-colors_and_type.css`). This file translates that CSS-variable-only mockup into a v4 `@theme` block that generates both utility classes **and** the original CSS variables.

# Porting the Dirt design system

The mockup defines everything as `:root { --foo: ... }`. That gives you the CSS variables but **no utility classes**. For the production `web-ui/`, we need both — Tailwind's strategy is to declare design tokens inside `@theme`, which emits them to `:root` automatically and wires up utilities.

## The complete styles.css block

This is the copy-ready entry point for `web-ui/src/styles.css`. Read [theme-configuration.md](theme-configuration.md) for the underlying mechanics.

```css
/* web-ui/src/styles.css
 * Dirt — paper/ink design system.
 * Light mode: aged paper. Dark mode: tent-at-lights-on.
 * Source of truth: debug/webapp.zip/colors_and_type.css (mirrored in
 * docs/references/tailwind-v4/raw/mockup-colors_and_type.css).
 */

@import "tailwindcss";

/* -------- font files -------- */
/* Fraunces is user-supplied; place the TTF under web-ui/src/fonts/. */
@font-face {
  font-family: 'Fraunces';
  src: url('./fonts/Fraunces-VariableFont_SOFT_WONK_opsz_wght.ttf') format('truetype-variations');
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}

/* Web fonts for IBM Plex Mono and Inter. If offline/self-hosted is required,
   download and add @font-face blocks for those too. */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap');

/* -------- runtime-switchable color tokens --------
   Declared as plain CSS variables so light/dark can flip them. The @theme
   block below references these via `@theme inline`, which makes utility
   classes (bg-paper, text-ink, etc.) resolve dynamically at the element
   scope — not frozen at build time. */

:root,
[data-theme="light"] {
  --dirt-paper:   #F3EBD8;
  --dirt-paper-2: #EBE0C6;
  --dirt-paper-3: #E2D5B4;

  --dirt-ink:   #1E1A14;
  --dirt-ink-2: #4A412E;
  --dirt-ink-3: #7A6F54;

  --dirt-rule:        rgba(30, 26, 20, 0.25);
  --dirt-rule-strong: rgba(30, 26, 20, 0.55);

  --dirt-accent-purple:  #5B2A82;
  --dirt-accent-magenta: #B22A6A;
  --dirt-leaf:           #5A6B3A;

  --dirt-sensor-temp:     #C8581F;
  --dirt-sensor-humidity: #2A6FA8;
  --dirt-sensor-vpd:      #4A6B38;
  --dirt-sensor-moisture: #7A4A24;

  --dirt-status-ok:   #4A6B38;
  --dirt-status-warn: #B87A1F;
  --dirt-status-err:  #9B2C2C;

  --dirt-plant-a: #D6A21C;
  --dirt-plant-b: #C86A1F;
  --dirt-plant-c: #C93D78;
  --dirt-plant-d: #2E6BB3;
}

[data-theme="dark"] {
  --dirt-paper:   #141612;
  --dirt-paper-2: #1C1E1A;
  --dirt-paper-3: #262822;

  --dirt-ink:   #ECE4D0;
  --dirt-ink-2: #B4A987;
  --dirt-ink-3: #7A7258;

  --dirt-rule:        rgba(236, 228, 208, 0.18);
  --dirt-rule-strong: rgba(236, 228, 208, 0.45);

  --dirt-accent-purple:  #B079E0;
  --dirt-accent-magenta: #F06AA8;
  --dirt-leaf:           #8AA167;

  --dirt-sensor-temp:     #FF8C42;
  --dirt-sensor-humidity: #42A5F5;
  --dirt-sensor-vpd:      #66BB6A;
  --dirt-sensor-moisture: #C08457;

  --dirt-status-ok:   #66BB6A;
  --dirt-status-warn: #E0A44B;
  --dirt-status-err:  #E06767;

  --dirt-plant-a: #E6B836;
  --dirt-plant-b: #E08545;
  --dirt-plant-c: #E06499;
  --dirt-plant-d: #5A9EE0;
}

/* -------- dark variant override --------
   Tells Tailwind's `dark:` variant to follow data-theme=dark instead of
   the OS media query. See variants-and-responsive.md. */
@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));

/* -------- @theme — generate utilities from tokens --------
   The `inline` option compiles utilities to the underlying var(--dirt-*)
   references, so they follow the [data-theme] switch at runtime.
   See theme-configuration.md for why `inline` is necessary here. */

@theme inline {
  /* palette */
  --color-paper:   var(--dirt-paper);
  --color-paper-2: var(--dirt-paper-2);
  --color-paper-3: var(--dirt-paper-3);

  --color-ink:   var(--dirt-ink);
  --color-ink-2: var(--dirt-ink-2);
  --color-ink-3: var(--dirt-ink-3);

  --color-rule:        var(--dirt-rule);
  --color-rule-strong: var(--dirt-rule-strong);

  --color-accent-purple:  var(--dirt-accent-purple);
  --color-accent-magenta: var(--dirt-accent-magenta);
  --color-leaf:           var(--dirt-leaf);

  --color-sensor-temp:     var(--dirt-sensor-temp);
  --color-sensor-humidity: var(--dirt-sensor-humidity);
  --color-sensor-vpd:      var(--dirt-sensor-vpd);
  --color-sensor-moisture: var(--dirt-sensor-moisture);

  --color-status-ok:   var(--dirt-status-ok);
  --color-status-warn: var(--dirt-status-warn);
  --color-status-err:  var(--dirt-status-err);

  --color-plant-a: var(--dirt-plant-a);
  --color-plant-b: var(--dirt-plant-b);
  --color-plant-c: var(--dirt-plant-c);
  --color-plant-d: var(--dirt-plant-d);
}

/* -------- @theme — static tokens (no runtime switch) -------- */

@theme {
  /* fonts — mockup uses Fraunces (serif brand), IBM Plex Mono (data),
     Inter (UI chrome). Not JetBrains Mono / Crimson Pro. */
  --font-serif: 'Fraunces', 'Iowan Old Style', 'Palatino Linotype', Palatino, Georgia, serif;
  --font-mono:  'IBM Plex Mono', 'SF Mono', Menlo, Consolas, 'Courier New', monospace;
  --font-sans:  'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;

  /* font-size scale from the mockup */
  --text-11: 11px;
  --text-12: 12px;
  --text-13: 13px;
  --text-14: 14px;
  --text-16: 16px;
  --text-18: 18px;
  --text-22: 22px;
  --text-28: 28px;
  --text-36: 36px;

  /* 4px spacing baseline — sets p-1 = 4px, p-2 = 8px, p-4 = 16px, etc. */
  --spacing: 4px;

  /* radius scale — mockup is sharp; 0 / 2px / 4px */
  --radius-none: 0;
  --radius-xs:   2px;
  --radius-sm:   4px;

  /* easing + duration */
  --ease-dirt: cubic-bezier(0.2, 0, 0, 1);
  --animate-duration-fast: 120ms;
  --animate-duration-std:  240ms;
}

/* -------- base layer — element defaults from the mockup -------- */

@layer base {
  html {
    font-family: var(--font-serif);
    font-size: var(--text-16);
    line-height: 1.55;
    color: var(--color-ink);
    background: var(--color-paper);
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }

  h1, h2, h3, h4, h5, h6 {
    font-family: var(--font-sans);
    font-weight: 600;
    letter-spacing: 0.01em;
    color: var(--color-ink);
    margin: 0;
  }
  h1 { font-size: var(--text-28); letter-spacing: -0.01em; }
  h2 { font-size: var(--text-18); }
  h3 {
    font-size: var(--text-14);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-ink-2);
  }

  /* Monospace treatment for numeric data. */
  code, kbd, samp, pre, time, .readout, .timestamp {
    font-family: var(--font-mono);
    font-size: 0.92em;
    font-variant-numeric: tabular-nums;
  }

  /* Always-visible focus ring — brand accent. */
  :focus-visible {
    outline: 2px solid var(--color-accent-magenta);
    outline-offset: 2px;
  }
}
```

## Brand wordmark

The mockup treats "Dirt" as italicized Fraunces. In components:

```tsx
<span className="font-serif italic text-ink text-28">Dirt</span>
```

If you want it as a reusable class, add a component utility:

```css
@layer components {
  .brand-wordmark {
    font-family: var(--font-serif);
    font-style: italic;
    font-weight: 500;
    letter-spacing: -0.01em;
  }
}
```

## Plant labels (A/B/C/D)

The plant sticker colors map to `bg-plant-a` through `bg-plant-d`:

```tsx
const plantLabels = {
  a: 'bg-plant-a',
  b: 'bg-plant-b',
  c: 'bg-plant-c',
  d: 'bg-plant-d',
} as const satisfies Record<PlantId, string>;

<span className={`inline-block w-2 h-2 border border-ink ${plantLabels[plant]}`} />
```

The `as const satisfies Record<…, string>` keeps classes **static strings** so Tailwind's source scanner picks them up. Do **not** generate them dynamically — `bg-plant-${id}` would be invisible to the scanner. See [directives.md](directives.md) for the safelist escape hatch if this ever becomes unavoidable.

## Sensor colors

Use `text-sensor-temp`, `text-sensor-humidity`, `text-sensor-vpd`, `text-sensor-moisture` for chart lines/labels. Values auto-flip between light and dark via the `@theme inline` block above.

## Status chips

`text-status-ok`, `text-status-warn`, `text-status-err`, paired with matching `border-*`:

```tsx
<span className="border border-status-ok text-status-ok uppercase text-11 px-1.5 tracking-wider">OK</span>
```

## Common mistakes

**Training-data default — hardcoding hex values instead of theme tokens:**

```tsx
// ❌ bypasses the theme; won't flip in dark mode
<div className="bg-[#F3EBD8] text-[#1E1A14]">
```

**Correct — use the token:**

```tsx
// ✅ flips via data-theme=dark because we used @theme inline
<div className="bg-paper text-ink">
```

**Training-data default — defining palette in `:root` only:**

```css
/* ❌ — variables exist, but no bg-paper / text-ink utilities */
:root {
  --color-paper: #F3EBD8;
  --color-ink: #1E1A14;
}
```

**Correct — wrap with `@theme` (plus `@theme inline` if runtime-switched):**

```css
/* ✅ */
@theme inline {
  --color-paper: var(--dirt-paper);
  --color-ink: var(--dirt-ink);
}
```
