---
title: Migration traps from v3
concept: tailwind-v4
updated: 2026-04-19
source: https://tailwindcss.com/docs/upgrade-guide
---

> Anchors agents against v3-era training data. Read this before accepting any Tailwind snippet suggested from recollection — v3 was the dominant version through most training data, and its patterns are wrong in v4. Every row in the tables below is something a fresh snippet is likely to get wrong.

# Migration traps from v3

For semantic upgrades (config → CSS, content array → auto-scan, `@tailwind` → `@import`, plugin API → directives), see:

- [install-vite.md](install-vite.md) — Vite wiring, `postcss.config.js` removal, `@tailwind` → `@import`
- [theme-configuration.md](theme-configuration.md) — `tailwind.config.js` → `@theme`
- [directives.md](directives.md) — `@layer utilities` → `@utility`, `@variants` → `@custom-variant`

This file is the flat, scannable list of **per-class and per-feature** traps.

## Automated migration tool

For existing v3 codebases, run the migration tool first:

```bash
npx @tailwindcss/upgrade
```

Requires Node.js 20+. Handles dependency updates, config → CSS conversion, and most class renames. Run on a clean branch, review diffs carefully, especially around custom plugins and `theme.extend`.

## Removed utilities — replace, don't re-add

| v3 | v4 replacement |
|---|---|
| `bg-opacity-50` | `bg-black/50` (slash syntax applies to any color utility) |
| `text-opacity-50` | `text-white/50` |
| `border-opacity-50` | `border-black/50` |
| `divide-opacity-50` | `divide-black/50` |
| `ring-opacity-50` | `ring-black/50` |
| `placeholder-opacity-50` | `placeholder-black/50` |
| `flex-shrink-0` | `shrink-0` |
| `flex-grow` | `grow` |
| `overflow-ellipsis` | `text-ellipsis` |
| `decoration-slice` | `box-decoration-slice` |
| `decoration-clone` | `box-decoration-clone` |

## Renamed utilities — size labels shifted one step

Shadow, drop-shadow, blur, backdrop-blur, and rounded scales shifted **downward**. v3's `shadow-sm` is now v4's `shadow-xs`; v3's bare `shadow` is now `shadow-sm`. Same for rounded/blur.

| v3 | v4 |
|---|---|
| `shadow-sm` | `shadow-xs` |
| `shadow` | `shadow-sm` |
| `drop-shadow-sm` | `drop-shadow-xs` |
| `drop-shadow` | `drop-shadow-sm` |
| `blur-sm` | `blur-xs` |
| `blur` | `blur-sm` |
| `backdrop-blur-sm` | `backdrop-blur-xs` |
| `backdrop-blur` | `backdrop-blur-sm` |
| `rounded-sm` | `rounded-xs` |
| `rounded` | `rounded-sm` |

If a layout looks suddenly off after porting v3 HTML, this is usually the cause.

## Ring and outline changes

| v3 | v4 | Why |
|---|---|---|
| `outline-none` | `outline-hidden` | v4's `outline-none` now sets `outline-style: none` (a11y regression); use `outline-hidden` for the v3 "focus-visible reset" behavior |
| `ring` (3px blue-500) | `ring-3 ring-blue-500` | default `ring` is now 1px `currentColor` |
| `ring-offset-2` | unchanged | — |

**Default border color:** v3 was `gray-200`, v4 is `currentColor`. Every `<div class="border">` needs an explicit `border-gray-200` (or a `@theme` token like `border-rule` in Dirt).

To preserve v3 behavior globally:

```css
@layer base {
  *, ::after, ::before, ::backdrop, ::file-selector-button {
    border-color: var(--color-gray-200, currentColor);
  }
}
```

## space-y / divide-y selector change

v4 changed the `space-y-*` / `divide-y-*` implementation to sidestep a slow v3 selector (`> :not([hidden]) ~ :not([hidden])`). It now uses `> :not(:last-child)` with bottom margin/border. The behavioral difference is subtle but real:

```css
/* v3 */
.space-y-4 > :not([hidden]) ~ :not([hidden]) { margin-top: 1rem; }

/* v4 */
.space-y-4 > :not(:last-child) { margin-bottom: 1rem; }
```

If you see unexpected spacing around `hidden` children, switch to `flex flex-col gap-4` (preferred in v4).

## Arbitrary value syntax — parens for CSS vars

| v3 | v4 |
|---|---|
| `bg-[--brand-color]` | `bg-(--brand-color)` |
| `fill-[--icon]` | `fill-(--icon)` |
| `text-[--ink]` | `text-(--ink)` |

Brackets still work for **literal** arbitrary values: `bg-[#ff0000]`, `top-[117px]`.

For grid/object-position lists: use underscores instead of commas (v3 auto-converted commas to spaces; v4 doesn't).

```html
<!-- ❌ v3 -->
<div class="grid-cols-[max-content,auto]">

<!-- ✅ v4 -->
<div class="grid-cols-[max-content_auto]">
```

## Important modifier position

```html
<!-- v3 -->
<div class="!flex !bg-red-500">

<!-- v4 — ! at end -->
<div class="flex! bg-red-500!">
```

## Transform resets

Transforms are now individual CSS properties (`rotate`, `scale`, `translate`) rather than a single `transform` combined value.

```html
<!-- v3 -->
<button class="scale-150 focus:transform-none">

<!-- v4 -->
<button class="scale-150 focus:scale-none">
```

Transitions of transforms must list the specific property:

```html
<!-- v3 -->
<button class="transition-[opacity,transform] hover:scale-150">

<!-- v4 -->
<button class="transition-[opacity,scale] hover:scale-150">
```

## Preflight changes (resets)

| Aspect | v3 | v4 | Mitigation |
|---|---|---|---|
| placeholder color | `gray-400` | current text color at 50% opacity | override in `@layer base` if jarring |
| `<button>` cursor | `pointer` | browser default (usually `default`) | add `@layer base { button:not(:disabled) { cursor: pointer; } }` |
| `<dialog>` | centered via margin auto | margins `0` | add `@layer base { dialog { margin: auto; } }` |
| `hidden` attribute | overridden by `block`, `flex`, etc. | wins over display utilities | remove `hidden` attribute or use `.hidden` class instead |

## JS plugin API — removed entirely

```js
// ❌ All of this is gone in v4
const plugin = require('tailwindcss/plugin');
module.exports = {
  plugins: [
    plugin(function({ addUtilities, addComponents, addVariant, theme }) { … }),
  ],
};
```

Replace with CSS-native equivalents:

- `addUtilities` → `@utility name { … }` (see [directives.md](directives.md))
- `addComponents` → `@layer components { .name { … } }`
- `addVariant` → `@custom-variant name (selector);`
- `theme('foo.bar')` in plugin → `var(--foo-bar)` in CSS

## `resolveConfig()` — removed

```ts
// ❌
import resolveConfig from 'tailwindcss/resolveConfig';
import config from './tailwind.config';
const full = resolveConfig(config);
full.theme.colors.blue['500'];
```

```ts
// ✅ Read CSS custom properties at runtime
const root = getComputedStyle(document.documentElement);
const magenta = root.getPropertyValue('--color-accent-magenta').trim();
```

## `corePlugins`, `safelist`, `container.center/padding`, `separator` — removed

| Removed config | v4 approach |
|---|---|
| `corePlugins: { ... }` | No replacement — all utilities are always available. Tree-shaking handles unused. |
| `safelist: ['bg-red-500']` | `@source inline("bg-red-500");` in CSS |
| `container.center: true` / `container.padding` | Define your own `.container` via `@utility container { … }` |
| `separator: '_'` | Not configurable; always `:` for variants |
| `prefix: 'tw-'` | `@import "tailwindcss" prefix(tw);` (see upgrade guide) |

## Gradient behavior

`bg-gradient-to-r` is now `bg-linear-to-r`. v4 also preserves intermediate gradient stops across variants (e.g. `dark:via-none` only clears the `via` stop, not the whole gradient), enabling cleaner dark-mode overrides.

## Hover on touch — now media-gated

`hover:` is wrapped in `@media (hover: hover)` automatically. Revert with `@custom-variant hover (&:hover);` only if you have a specific need (rare).
