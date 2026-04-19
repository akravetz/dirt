---
title: Theme configuration with @theme
concept: tailwind-v4
updated: 2026-04-19
source: https://tailwindcss.com/docs/theme
---

> Anchors agents to current Tailwind CSS v4.2.x theme practice. Prefer what you read here over training-data instincts — v4 has no `tailwind.config.js` and no `theme.extend`. Design tokens live in a CSS `@theme { }` block, and each token is both a generator for utility classes and a publicly-exposed CSS variable.

# Theme configuration with @theme

In v4, the theme is defined in CSS, not JavaScript. The `@theme` block lives in `web-ui/src/styles.css` (or any file imported from it) and serves two purposes simultaneously:

1. Each `--namespace-name` declaration **generates utility classes** (e.g. `--color-accent-magenta: #B22A6A;` produces `bg-accent-magenta`, `text-accent-magenta`, `border-accent-magenta`, `ring-accent-magenta`, `fill-accent-magenta`, `stroke-accent-magenta`, etc.).
2. Each declaration is also **emitted as a CSS custom property on `:root`**, so `var(--color-accent-magenta)` is usable anywhere — in custom CSS, inline styles, or JavaScript via `getComputedStyle`.

That dual behavior is the point of `@theme`. A plain `:root { --foo: ... }` block gives you the variable but **does not** generate utilities.

## Syntax

```css
@import "tailwindcss";

@theme {
  --color-accent-magenta: #B22A6A;
  --font-serif: "Fraunces", Georgia, serif;
  --breakpoint-3xl: 120rem;
}
```

`@theme` must be top-level — not nested inside `:root`, media queries, or a `@layer`.

## Namespaces — each maps to a family of utilities

| Namespace | Generates | Example declaration → class |
|---|---|---|
| `--color-*` | `bg-*`, `text-*`, `border-*`, `ring-*`, `fill-*`, `stroke-*`, `outline-*`, `shadow-*`, `accent-*`, `caret-*`, `decoration-*` | `--color-ink: #1E1A14;` → `bg-ink`, `text-ink`, … |
| `--font-*` | `font-*` (font-family) | `--font-serif: "Fraunces";` → `font-serif` |
| `--text-*` | `text-*` (font-size) | `--text-xl: 1.25rem;` → `text-xl` |
| `--font-weight-*` | `font-*` (weight) | `--font-weight-bold: 700;` → `font-bold` |
| `--tracking-*` | `tracking-*` | `--tracking-wide: 0.025em;` → `tracking-wide` |
| `--leading-*` | `leading-*` | `--leading-tight: 1.25;` → `leading-tight` |
| `--breakpoint-*` | responsive variants `sm:`, `md:`, etc. | `--breakpoint-xl: 80rem;` → `xl:*` |
| `--container-*` | container-query variants `@sm:`, `@md:`, and `max-w-*` | `--container-md: 28rem;` → `@md:*` |
| `--spacing` (scalar) or `--spacing-*` | `p-*`, `m-*`, `gap-*`, `w-*`, `h-*`, `inset-*`, etc. | `--spacing: 0.25rem;` → `p-4` means `1rem` |
| `--radius-*` | `rounded-*` | `--radius-lg: 0.5rem;` → `rounded-lg` |
| `--shadow-*` | `shadow-*` | `--shadow-md: 0 4px 6px …;` → `shadow-md` |
| `--inset-shadow-*` | `inset-shadow-*` | |
| `--drop-shadow-*` | `drop-shadow-*` | |
| `--blur-*` | `blur-*` | |
| `--perspective-*` | `perspective-*` | |
| `--aspect-*` | `aspect-*` | `--aspect-video: 16/9;` → `aspect-video` |
| `--ease-*` | `ease-*` transition timing | |
| `--animate-*` | `animate-*` | `--animate-spin: spin 1s linear infinite;` → `animate-spin` |

The full default set lives in `raw/tailwindcss-theme.css` (510 lines). Read it when you need to know a default value or whether a namespace exists.

## Extend vs override vs reset

**Extend** (default): declare a new value. It coexists with defaults.

```css
@theme {
  --color-accent-magenta: #B22A6A;
  /* All default colors remain: red-500, blue-400, gray-800, etc. */
}
```

**Override** a single default: declare the same variable.

```css
@theme {
  --breakpoint-sm: 30rem;  /* was 40rem */
  --color-red-500: oklch(0.637 0.237 25.331);
}
```

**Remove** one value: set to `initial`.

```css
@theme {
  --breakpoint-2xl: initial;  /* drops the 2xl: variant */
}
```

**Reset an entire namespace** then add only what you want:

```css
@theme {
  --color-*: initial;
  --color-paper: #F3EBD8;
  --color-ink: #1E1A14;
  --color-accent-magenta: #B22A6A;
  /* No more blue-500, red-500, etc. — only these three. */
}
```

**Reset everything** (rare, only when building a fully custom design system):

```css
@theme {
  --*: initial;
  --spacing: 4px;
  --color-paper: #F3EBD8;
  /* ... */
}
```

## @theme inline — reference another variable

If a theme variable is a `var()` reference to another variable that changes between contexts (e.g. a light/dark CSS variable defined in `:root`), wrap the block with `inline`:

```css
:root {
  --dirt-canvas: #F3EBD8;
}
[data-theme="dark"] {
  --dirt-canvas: #141612;
}

@theme inline {
  --color-paper: var(--dirt-canvas);
}
```

Without `inline`, the generated utility would be `.bg-paper { background-color: var(--color-paper); }` — and `--color-paper` is defined once on `:root` at build time, so it can't follow the `[data-theme="dark"]` switch. With `inline`, the utility is compiled to `.bg-paper { background-color: var(--dirt-canvas); }`, so it resolves at the element's scope and picks up the dark override. Use `inline` whenever a theme value depends on another CSS variable that changes at runtime.

## Reading theme values in custom CSS

Every `@theme` variable is a real CSS custom property on `:root`:

```css
@layer components {
  .card {
    background-color: var(--color-paper-2);
    border: 1px solid var(--color-rule);
    border-radius: var(--radius-sm);
    padding: var(--spacing-4);
    font-family: var(--font-sans);
  }
}
```

Prefer `var(--color-foo)` over the `theme()` function. `theme()` still works for media queries (`@media (width >= theme(--breakpoint-xl))`) but is otherwise discouraged in v4.

## Reading theme values in JavaScript

There is **no** `resolveConfig()` export. Read the CSS variables:

```ts
const root = getComputedStyle(document.documentElement);
const magenta = root.getPropertyValue('--color-accent-magenta').trim();
// "#B22A6A"
```

## The full Dirt `@theme` block

See [project-design-system.md](project-design-system.md) for the copy-ready `@theme` block that ports `debug/webapp.zip/colors_and_type.css` into v4 form.

## Common mistakes

**Training-data default — v3 JS config with `theme.extend`:**

```js
// ❌ tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        paper: '#F3EBD8',
        ink: '#1E1A14',
        'accent-magenta': '#B22A6A',
      },
      fontFamily: {
        serif: ['Fraunces', 'Georgia', 'serif'],
      },
    },
  },
};
```

**v4 correct — in CSS, flat keys:**

```css
/* ✅ web-ui/src/styles.css */
@import "tailwindcss";

@theme {
  --color-paper: #F3EBD8;
  --color-ink: #1E1A14;
  --color-accent-magenta: #B22A6A;
  --font-serif: "Fraunces", Georgia, serif;
}
```

Note the shape difference: **no nesting**, no `extend:` vs `override:` distinction (declaring a new key extends; declaring an existing key overrides; `initial` removes).

**Training-data default — `@layer base { :root { --foo: ... } }` to define a token:**

```css
/* ❌ — puts the variable in :root but does NOT generate utility classes */
@layer base {
  :root {
    --color-accent-magenta: #B22A6A;
  }
}
```

The CSS variable exists, but `bg-accent-magenta` and friends **do not**. Use `@theme { --color-accent-magenta: #B22A6A; }` instead — that block does both.
