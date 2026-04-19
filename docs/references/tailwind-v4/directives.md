---
title: Directives — @import, @layer, @utility, @custom-variant, @source, @apply, @reference
concept: tailwind-v4
updated: 2026-04-19
source: https://tailwindcss.com/docs/adding-custom-styles
---

> Anchors agents to current Tailwind CSS v4.2.x directive usage. Training data will suggest v3 at-rules (`@tailwind base/components/utilities`, `@layer utilities { .foo {} }` for custom utilities, `@variants` for variant generation) — all superseded in v4.

# Directives

Every v4 at-rule, what it does, what it replaces.

## @import "tailwindcss"

The single entry point. Replaces v3's three `@tailwind` directives.

```css
@import "tailwindcss";
```

This line expands (at build time) to:

```css
@layer theme, base, components, utilities;
@import "tailwindcss/theme.css" layer(theme);
@import "tailwindcss/preflight.css" layer(base);
@import "tailwindcss/utilities.css" layer(utilities);
```

See `raw/tailwindcss-index.css` for the source. You rarely need to think about the layer cascade, but knowing it helps debug specificity problems — your own `@theme` and `@utility` blocks land in `theme` and `utilities` respectively.

## @layer — author base and component styles

Use `@layer base` for global resets and element-level defaults (typography, link styles, focus rings):

```css
@layer base {
  html {
    font-family: var(--font-serif);
    color: var(--color-ink);
    background: var(--color-paper);
  }
  h1 {
    font-family: var(--font-sans);
    font-size: var(--text-2xl);
    font-weight: 600;
  }
  :focus-visible {
    outline: 2px solid var(--color-accent-magenta);
    outline-offset: 2px;
  }
}
```

Use `@layer components` for reusable named classes that can be overridden by utilities:

```css
@layer components {
  .card {
    background: var(--color-paper-2);
    border: 1px solid var(--color-rule);
    border-radius: var(--radius-sm);
    padding: var(--spacing-4);
  }
}
```

`.card` then takes lower precedence than any utility, so `<div class="card rounded-none">` wins the rounded-none.

**Do not** use `@layer utilities { .my-util { ... } }` for new utilities. That pattern is v3. In v4, use `@utility` (below).

## @utility — define custom utilities

Replaces v3's `@layer utilities { ... }` wrapper. Flat, no `@layer`:

```css
@utility scrollbar-hidden {
  scrollbar-width: none;
  &::-webkit-scrollbar {
    display: none;
  }
}
```

Usage: `<div class="scrollbar-hidden">` — and all variants (`hover:scrollbar-hidden`, `md:scrollbar-hidden`) work automatically.

### Functional utilities

Suffix the name with `-*` and use `--value()` to map to theme tokens, bare values, or arbitrary values:

```css
/* Only matches --tab-size-* theme tokens */
@utility tab-* {
  tab-size: --value(--tab-size-*);
}

/* Matches bare integers: tab-1, tab-2, tab-76 */
@utility tab-* {
  tab-size: --value(integer);
}

/* Matches arbitrary values: tab-[4] */
@utility tab-* {
  tab-size: --value([integer]);
}

/* All three at once */
@utility tab-* {
  tab-size: --value(--tab-size-*, integer, [integer]);
}
```

Add `--modifier()` for the post-slash portion of a utility (like the `/16` in `text-xl/16`):

```css
@utility text-* {
  font-size: --value(--text-*, [length]);
  line-height: --modifier(--leading-*, [length], [*]);
}
```

## @custom-variant — define custom variants

Replaces v3's `plugin()` + `addVariant()` JS API. The most common use is overriding dark mode:

```css
/* Class-based dark mode */
@custom-variant dark (&:where(.dark, .dark *));

/* Data-attribute dark mode (preferred for Dirt — matches mockup) */
@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));
```

The single-line shorthand is equivalent to:

```css
@custom-variant dark {
  &:where([data-theme=dark], [data-theme=dark] *) {
    @slot;
  }
}
```

Custom variants for other patterns:

```css
@custom-variant theme-midnight (&:where([data-theme=midnight] *));
@custom-variant any-hover (@media (any-hover: hover) { &:hover { @slot; } });
```

Usage in markup: `<button class="theme-midnight:bg-black any-hover:underline">`.

## @apply — inline utility classes into custom CSS

Supported, but use sparingly. Prefer `var(--color-*)` over `@apply bg-color-*`; `@apply` is most useful when you want the exact utility's cascade behavior (including variants).

```css
@layer components {
  .btn-primary {
    @apply rounded-sm px-3 py-1.5 font-medium;
    background: var(--color-ink);
    color: var(--color-paper);
  }
}
```

### @reference — use @apply in scoped stylesheets

When `@apply` is used in a file that doesn't directly `@import "tailwindcss"` (e.g. CSS Modules, Vue `<style>`, Svelte `<style>`, Astro component styles), prepend `@reference`:

```vue
<style>
@reference "../../styles.css";
h1 {
  @apply text-2xl font-bold text-ink;
}
</style>
```

This gives the scoped stylesheet visibility into theme variables and custom utilities **without duplicating them into the output**. For plain React components with global CSS (the default in Dirt `web-ui/`), `@reference` is not needed.

## @source — explicit source paths

Tailwind v4 scans the project automatically. Use `@source` only to augment that behavior:

```css
/* Add an external library as a source */
@source "../node_modules/@acmecorp/ui-lib";

/* Exclude a directory */
@source not "./src/legacy";

/* Safelist classes that are constructed dynamically or live in string literals.
   Useful for class names produced by string concatenation — Tailwind won't
   detect those at build time. */
@source inline("bg-accent-magenta text-paper");

/* With variants via brace expansion */
@source inline("{hover:,focus:,}underline");
@source inline("bg-plant-{a,b,c,d}");

/* Explicitly exclude */
@source not inline("bg-red-{50,100,200,300,400,500,600,700,800,900,950}");

/* Disable auto-scan and list everything explicitly (multi-package monorepo) */
@import "tailwindcss" source(none);
@source "../apps/admin";
@source "../packages/shared";

/* Change the auto-scan base directory (when tooling runs from a parent dir) */
@import "tailwindcss" source("../src");
```

### When to use `@source inline(...)`

Only when class names are **constructed from runtime strings** — e.g. `bg-${color}-500` in a component prop. Tailwind reads source files as plain text; it cannot see through template interpolation.

Fix the root cause when you can. Instead of `bg-${color}-500`, use a static mapping:

```tsx
const tone = {
  ok: 'bg-status-ok text-paper',
  warn: 'bg-status-warn text-ink',
  err: 'bg-status-err text-paper',
} as const satisfies Record<Tone, string>;

<span className={tone[status]}>…</span>
```

This pattern is detectable by the scanner and doesn't need safelisting.

## Arbitrary values — brackets vs parentheses

Literal arbitrary values use brackets:

```html
<div class="bg-[#ff0000] top-[117px] grid-cols-[max-content_auto]">
```

CSS variable references use **parentheses** (v4 change from v3 brackets):

```html
<!-- v4 -->
<div class="bg-(--brand-color) fill-(--icon-color)">

<!-- v3 — do NOT use in v4 -->
<div class="bg-[--brand-color]">
```

Spaces inside arbitrary values must be underscores: `grid-cols-[1fr_500px_2fr]`. Commas stay as commas in most positions (v3's comma-to-space rewrite is gone); for grid/object-position lists, underscores replace commas: `grid-cols-[max-content_auto]` not `grid-cols-[max-content,auto]`.

## Common mistakes

**Training-data default — v3 custom utility via `@layer`:**

```css
/* ❌ v3 pattern */
@layer utilities {
  .scrollbar-hidden::-webkit-scrollbar {
    display: none;
  }
  .scrollbar-hidden {
    scrollbar-width: none;
  }
}
```

**v4 correct:**

```css
/* ✅ */
@utility scrollbar-hidden {
  scrollbar-width: none;
  &::-webkit-scrollbar {
    display: none;
  }
}
```

**Training-data default — dark mode in JS config:**

```js
// ❌ tailwind.config.js
module.exports = {
  darkMode: ['class', '[data-theme="dark"]'],
};
```

**v4 correct:**

```css
/* ✅ styles.css */
@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));
```

**Training-data default — CSS-var arbitrary in square brackets:**

```html
<!-- ❌ v3 -->
<div class="bg-[--accent-magenta]">
```

**v4 correct — parentheses:**

```html
<!-- ✅ v4 -->
<div class="bg-(--accent-magenta)">
```
