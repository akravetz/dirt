---
title: Tailwind CSS v4 Reference Pack
concept: tailwind-v4
mode: framework
version: 4.2.2
updated: 2026-04-19
---

# Tailwind CSS v4

This pack anchors agents to Tailwind CSS **v4.2.x** (first stable: v4.0 shipped Jan 2025). v4 is a ground-up rewrite with a **new Rust-based engine (Oxide)**, **CSS-first configuration** (no more `tailwind.config.js`), **automatic content detection**, and a redesigned theme system built on CSS custom properties. Every major piece of the API surface from v3 has moved.

This is the reference for the `web-ui/` app: **Vite + React + TypeScript**, using the `@tailwindcss/vite` plugin. The global stylesheet lives at `web-ui/src/styles.css` and is imported once from `main.tsx`. Phase 2 generator agents will author most UI against this setup — pack should keep them consistent across sessions.

## When to consult this pack

Read this INDEX before writing or refactoring any Tailwind utility class in `web-ui/src/`, editing `web-ui/src/styles.css` (global `@import "tailwindcss"` + `@theme` block), tuning `vite.config.ts` for `@tailwindcss/vite`, adding custom utilities with `@utility`, setting up the paper/ink/magenta palette in `@theme`, wiring dark mode, or porting the design-system custom properties from `debug/webapp.zip/colors_and_type.css`. Prefer what's here over training-data recollection — training data overwhelmingly suggests v3 patterns (`tailwind.config.js`, `@tailwind base/components/utilities`, `content: []`, `autoprefixer`, `postcss-import`), all of which are obsolete or wrong in v4.

## Project context (keep embedded)

- **App scaffold:** `web-ui/` (Vite + React + TS). Not yet instantiated — when created, Tailwind must be wired via `@tailwindcss/vite` in `vite.config.ts`, **not** PostCSS + `autoprefixer`.
- **Single global stylesheet:** `web-ui/src/styles.css`. It must start with `@import "tailwindcss";` (v3's three `@tailwind` directives are gone). Imported exactly once, from `main.tsx`.
- **Design tokens to port** (see `raw/mockup-colors_and_type.css` for source of truth):
  - Palette: paper `#F3EBD8` / paper-2 `#EBE0C6` / paper-3 `#E2D5B4`, ink `#1E1A14` / ink-2 `#4A412E` / ink-3 `#7A6F54`, accent-magenta `#B22A6A`, accent-purple `#5B2A82`, leaf `#5A6B3A`, plant-a..d sticker colors.
  - Fonts: **Fraunces** (variable, user-supplied TTF, brand serif — italic when used as wordmark), **IBM Plex Mono** (numbers/data/timestamps, `tabular-nums`), **Inter** (UI chrome). Pack topics show how to expose these as `font-serif` / `font-mono` / `font-sans` via `@theme`.
  - Dark mode via `data-theme="dark"` on the root element. Use `@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));`.
- **Browser floor:** v4 requires Safari 16.4+, Chrome 111+, Firefox 128+. Relies on `@property` and `color-mix()`. If you need to support older browsers, v4 is the wrong dependency — flag it.

## Topics

- **[Install and Vite setup](install-vite.md)** — Read first when scaffolding `web-ui/` or wiring Tailwind into an existing Vite project. Covers `@tailwindcss/vite`, `vite.config.ts`, `src/styles.css` entry, and what to delete from v3 setups (`tailwind.config.js`, `postcss.config.js`, `autoprefixer`).
- **[Theme configuration with @theme](theme-configuration.md)** — Read when adding colors, fonts, spacing, radii, or breakpoints. Covers namespace → utility mapping, `@theme inline`, `initial` resets, and the full port of the Dirt mockup palette.
- **[Directives: @import, @layer, @utility, @custom-variant, @source, @apply](directives.md)** — Read when editing `styles.css` structure, adding custom utilities or variants, safelisting dynamic classes, or using `@apply` in component styles. Covers every v4 at-rule and how it replaces a v3 pattern.
- **[Dark mode and responsive design](variants-and-responsive.md)** — Read when wiring theme toggling (`data-theme="dark"`), customizing breakpoints, or using container queries. Covers `@custom-variant dark`, max-width variants, `@container` variants, and default breakpoint/container scales.
- **[Porting the Dirt design system](project-design-system.md)** — Read when porting `debug/webapp.zip/colors_and_type.css` into `web-ui/src/styles.css`. Provides a complete, copy-ready `@theme` block for the paper/ink palette, Fraunces/Plex Mono/Inter fonts, spacing scale, and dark-mode `@custom-variant`.
- **[Migration traps from v3](migration-traps.md)** — Read before accepting any Tailwind snippet your training data produced. Side-by-side v3 → v4 corrections for every common anti-pattern: config file, directives, PostCSS, renamed utilities, opacity syntax, `@layer utilities` → `@utility`, arbitrary-value CSS-var brackets → parens, `outline-none`, ring defaults, space-y performance, hover on touch.

## Version-specific warnings

The following v3 patterns are pervasive in training data and **wrong in v4**. Do not accept a snippet that uses any of them without first correcting to the v4 equivalent.

- `tailwind.config.js` with `content: [...]`, `theme: { extend: { ... } }`, `plugins: [...]` — **removed**. Configure via `@theme { ... }` in `styles.css`. See [theme-configuration.md](theme-configuration.md).
- `@tailwind base; @tailwind components; @tailwind utilities;` — **removed**. Use `@import "tailwindcss";` (single line). See [directives.md](directives.md).
- `postcss.config.js` with `tailwindcss` + `autoprefixer` + `postcss-import` — **wrong** for a Vite project. Use `@tailwindcss/vite` plugin in `vite.config.ts`; autoprefixer/import are handled internally. See [install-vite.md](install-vite.md).
- `bg-opacity-50`, `text-opacity-50`, `ring-opacity-*`, `border-opacity-*` — **removed**. Use slash syntax: `bg-black/50`, `text-white/75`. See [migration-traps.md](migration-traps.md).
- `flex-shrink-0`, `flex-grow-0`, `overflow-ellipsis`, `decoration-slice` — **removed**. Use `shrink-0`, `grow-0`, `text-ellipsis`, `box-decoration-slice`.
- `shadow-sm` / `shadow` / `rounded-sm` / `rounded` / `blur-sm` / `blur` — **renamed**. In v4, `shadow-sm` is the old `shadow-xs` etc. See the rename table in [migration-traps.md](migration-traps.md).
- `outline-none` — **semantics changed**: now sets `outline-style: none` (a11y regression). Use `outline-hidden` for the v3 focus-ring reset behavior.
- `ring` (default 3px blue-500) — v4 default is 1px `currentColor`. Use `ring-3 ring-blue-500` to get the old look.
- Default `border` color — v3 was `gray-200`, v4 is `currentColor`. Every `<div class="border">` now needs `border-gray-200` (or a `@theme` override).
- `@layer utilities { .my-util { ... } }` for custom utilities — **replaced** by `@utility my-util { ... }`. Flat, no `@layer` wrapper. See [directives.md](directives.md).
- Arbitrary CSS-variable syntax `bg-[--brand]` — **changed** to `bg-(--brand)` (parentheses, not brackets). Brackets are now only for literal arbitrary values (`bg-[#ff0000]`).
- `darkMode: 'class'` in config — **removed**. Declare in CSS: `@custom-variant dark (&:where(.dark, .dark *));`. See [variants-and-responsive.md](variants-and-responsive.md).
- `module.exports = { plugins: [...] }` and any `tailwindcss/plugin` imports — v4 has **no JS plugin API**. Replace plugins with `@utility` / `@custom-variant` / theme variables.
- `resolveConfig()` from `tailwindcss` package — **removed**. If you need a theme value in JS, read the generated CSS variable: `getComputedStyle(document.documentElement).getPropertyValue('--color-accent-magenta')`.

## Sources

- https://tailwindcss.com/docs/upgrade-guide
- https://tailwindcss.com/docs/installation/using-vite
- https://tailwindcss.com/docs/theme
- https://tailwindcss.com/docs/adding-custom-styles
- https://tailwindcss.com/docs/detecting-classes-in-source-files
- https://tailwindcss.com/docs/dark-mode
- https://tailwindcss.com/docs/responsive-design
- https://tailwindcss.com/docs/colors
- https://github.com/tailwindlabs/tailwindcss (v4.2.2 source — see `raw/`)
- `debug/webapp.zip/colors_and_type.css` (Dirt mockup design tokens — see `raw/mockup-colors_and_type.css`)
