---
title: Install and Vite setup
concept: tailwind-v4
updated: 2026-04-19
source: https://tailwindcss.com/docs/installation/using-vite
---

> Anchors agents to current Tailwind CSS v4.2.x practice. Prefer what you read here over training-data instincts — v4 scraps the v3 install flow (`tailwind.config.js`, `postcss.config.js`, `@tailwind` directives, `autoprefixer`). If training data suggests any of those, stop and follow this file.

# Install and Vite setup

Target: the `web-ui/` directory in this repo — Vite + React + TypeScript. The goal is a one-stylesheet setup (`web-ui/src/styles.css`) imported once from `main.tsx`, with Tailwind wired as a Vite plugin.

## Install

From `web-ui/`:

```bash
npm install tailwindcss @tailwindcss/vite
```

Do **not** install `autoprefixer`, `postcss`, `postcss-import`, `postcss-nesting`, `postcss-cli`, or `@tailwindcss/postcss`. v4's Oxide engine handles nesting, vendor prefixes, and `@import` inlining internally. PostCSS isn't in the path for a Vite project.

Also do **not** install `tailwindcss-animate`, `@tailwindcss/typography`, or `@tailwindcss/forms` preemptively — the v3 plugin ecosystem doesn't directly apply to v4's new plugin model, and the defaults are much richer. Add each only when a specific feature needs it.

## vite.config.ts

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
});
```

The `tailwindcss()` plugin takes no required options. It scans source files, compiles the stylesheet on demand, and hot-reloads on theme or class changes.

## The single global stylesheet

`web-ui/src/styles.css`:

```css
@import "tailwindcss";

/* Your @theme, @custom-variant, @utility blocks go below. */
/* See theme-configuration.md for the full Dirt @theme block. */
```

That one line replaces all three of v3's `@tailwind base; @tailwind components; @tailwind utilities;` directives. It also injects preflight (v4's reset) and all utility classes, gated by source detection.

## Import the stylesheet exactly once

`web-ui/src/main.tsx`:

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';  // exactly once, here

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

Do not import `styles.css` from individual components. v4 bundles the whole utility sheet at the root — importing per-component will bloat the graph and can cause ordering bugs with `@layer`.

## index.html

```html
<!doctype html>
<html lang="en" data-theme="light">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Dirt</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

The `data-theme="light"` attribute pairs with the `@custom-variant dark` block described in [variants-and-responsive.md](variants-and-responsive.md). JavaScript flips it between `"light"` and `"dark"`.

## Source detection — the content: [] replacement

**There is no `content: [...]` array in v4.** The Oxide engine automatically scans every file in the project except those in `.gitignore`, `node_modules`, binary files, CSS files, and lockfiles. For a standard Vite + React app inside `web-ui/`, no configuration is needed.

Register extra sources only when needed, in the stylesheet:

```css
@import "tailwindcss";

/* Pull classes from a UI library that lives in node_modules. */
@source "../node_modules/@acmecorp/ui-lib";

/* Exclude a legacy directory. */
@source not "./src/legacy";

/* Safelist a class that only appears in dynamic string concatenation. */
@source inline("bg-accent-magenta");
```

See [directives.md](directives.md) for the full `@source` syntax.

## What to delete if migrating from a v3 project

- `tailwind.config.js` / `tailwind.config.ts` / `tailwind.config.cjs`
- `postcss.config.js` / `postcss.config.cjs` / `postcss.config.mjs`
- `autoprefixer`, `postcss`, `postcss-import`, `postcss-nesting` from `package.json`
- The three `@tailwind base;` / `@tailwind components;` / `@tailwind utilities;` lines
- Any `import tailwindcss from 'tailwindcss'` in a PostCSS config

If the project already has a v3 `tailwind.config.js` that you want to preserve during migration, `@import "tailwindcss";` + `@config "../../tailwind.config.js";` works as a backward-compat bridge — but don't do this for a new project. Port the config to `@theme` directly; see [theme-configuration.md](theme-configuration.md).

## Browser requirements

v4 requires Safari 16.4+, Chrome 111+, Firefox 128+. It uses `@property` (for registered custom properties) and `color-mix()`. If the project needs to support older browsers, flag it — v4 is the wrong dependency.

## Common mistakes

**Training-data default — v3 PostCSS setup:**

```js
// ❌ postcss.config.js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

```js
// ❌ tailwind.config.js
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
```

```css
/* ❌ src/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

**v4 correct — no config files, Vite plugin, one @import:**

```ts
// ✅ vite.config.ts
import tailwindcss from '@tailwindcss/vite';
export default defineConfig({ plugins: [react(), tailwindcss()] });
```

```css
/* ✅ src/styles.css */
@import "tailwindcss";
```

No `tailwind.config.js`, no `postcss.config.js`, no `autoprefixer`. Source detection is automatic.
