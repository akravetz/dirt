---
title: Dark mode, variants, and responsive design
concept: tailwind-v4
updated: 2026-04-19
source: https://tailwindcss.com/docs/dark-mode
---

> Anchors agents to current Tailwind CSS v4.2.x variant and responsive practice. Training data will suggest `darkMode: 'class'` in JS config and the v3 `sm:max-md:` stacking order — both changed in v4.

# Dark mode, variants, and responsive design

## Dark mode

### Default behavior — prefers-color-scheme

Out of the box, `dark:` tracks the OS setting. No config needed:

```html
<div class="bg-paper dark:bg-ink text-ink dark:text-paper">
  …
</div>
```

### Data-attribute dark mode (use this for Dirt)

The Dirt mockup toggles via `data-theme="dark"` on `<html>`. Override the `dark` variant in CSS:

```css
/* web-ui/src/styles.css */
@import "tailwindcss";

@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));
```

The `&:where(...)` wrapper is important: it matches both the element carrying `data-theme="dark"` and all its descendants, and the `:where()` keeps specificity at zero so utilities still override cleanly.

HTML:

```html
<html data-theme="dark">
  <body>
    <div class="bg-paper dark:bg-ink">…</div>
  </body>
</html>
```

### Class-based alternative

If you prefer `class="dark"` on the root:

```css
@custom-variant dark (&:where(.dark, .dark *));
```

```html
<html class="dark">…</html>
```

### Toggling from JavaScript

Standard three-way toggle (inline in `<head>` to avoid FOUC):

```html
<script>
  // Run before React mounts
  const stored = localStorage.theme;
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = stored ?? (prefersDark ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', theme);
</script>
```

Then in app code:

```ts
function setTheme(theme: 'light' | 'dark' | 'system') {
  if (theme === 'system') {
    localStorage.removeItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
  } else {
    localStorage.theme = theme;
    document.documentElement.setAttribute('data-theme', theme);
  }
}
```

## Responsive design

### Default breakpoints

| Variant | Width | Use at |
|---|---|---|
| `sm:` | `≥ 40rem` (640px) | small phones landscape / large phones |
| `md:` | `≥ 48rem` (768px) | tablets portrait |
| `lg:` | `≥ 64rem` (1024px) | tablets landscape / small laptops |
| `xl:` | `≥ 80rem` (1280px) | desktop |
| `2xl:` | `≥ 96rem` (1536px) | wide desktop |

Mobile-first. Unprefixed utilities apply everywhere; prefixed utilities apply at that breakpoint **and up**:

```html
<!-- Center on mobile, left-align from sm and up -->
<div class="text-center sm:text-left">
```

### max-* variants for upper bounds

```html
<!-- Only below md (i.e. ≤ 767px) -->
<div class="max-md:hidden">

<!-- Between md and xl (i.e. ≥ 768px AND < 1280px) -->
<div class="md:max-xl:grid-cols-2">
```

### Arbitrary breakpoints

```html
<div class="min-[900px]:grid-cols-3 max-[599px]:flex-col">
```

### Customizing breakpoints

Add, override, or remove breakpoints in `@theme`:

```css
@theme {
  --breakpoint-xs: 30rem;     /* adds xs: */
  --breakpoint-2xl: 100rem;   /* overrides default */
  --breakpoint-3xl: initial;  /* — not needed, just shown for syntax; you add 3xl below */
  --breakpoint-3xl: 120rem;   /* adds 3xl: */
}
```

Replace all:

```css
@theme {
  --breakpoint-*: initial;
  --breakpoint-tablet: 40rem;
  --breakpoint-laptop: 64rem;
  --breakpoint-desktop: 80rem;
}
```

## Container queries

Container queries use `@container` on a parent, then `@sm:` / `@md:` / etc. on descendants. Default sizes `@3xs` through `@7xl` (256px to 1280px) are defined in `raw/tailwindcss-theme.css`.

```html
<div class="@container">
  <div class="flex flex-col @md:flex-row @2xl:gap-8">…</div>
</div>
```

Named containers (when you have nested `@container` elements):

```html
<div class="@container/outer">
  <div class="@container/inner">
    <div class="@md/outer:hidden @md/inner:flex">…</div>
  </div>
</div>
```

Customize container sizes:

```css
@theme {
  --container-8xl: 96rem;  /* adds @8xl: */
}
```

## Variant stacking order (v3 → v4 reversal)

**Variants now stack left-to-right** instead of right-to-left. This matches CSS's natural reading order and is a silent change — the same class string can compile to different CSS than in v3.

```html
<!-- v3 — applied as first(:pt-0) against each * child -->
<ul class="first:*:pt-0 last:*:pb-0">

<!-- v4 — applied as *(:first:pt-0) against each * child -->
<ul class="*:first:pt-0 *:last:pb-0">
  <li>…</li>
  <li>…</li>
</ul>
```

Read modifier chains left-to-right: `md:max-xl:hover:bg-ink` = "at md and above, also at less than xl, on hover, set bg to ink."

## Hover on touch devices

v4 wraps `hover:` in `@media (hover: hover)` automatically, so hover styles don't stick on tap on touch devices. If you need the old always-on behavior:

```css
@custom-variant hover (&:hover);
```

## Common mistakes

**Training-data default — `darkMode` in JS config:**

```js
// ❌
module.exports = { darkMode: 'class' };
```

**v4 correct:**

```css
/* ✅ */
@custom-variant dark (&:where(.dark, .dark *));
```

**Training-data default — v3 variant stacking:**

```html
<!-- ❌ v3 order, wrong selector in v4 -->
<li class="first:*:pt-0">
```

**v4 correct:**

```html
<!-- ✅ -->
<li class="*:first:pt-0">
```
