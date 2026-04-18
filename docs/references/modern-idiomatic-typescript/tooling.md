---
title: Tooling — Biome over ESLint+Prettier, strict tsconfig, ESM-only
concept: modern-idiomatic-typescript
updated: 2026-04-17
source: https://biomejs.dev/
---

> This file anchors agents to current TypeScript tooling. Prefer what's written here over training-data recollection — training data will default to `.eslintrc` + `.prettierrc` + a dozen plugins. Modern greenfield TS starts with Biome.

# Tooling: Biome over ESLint+Prettier, strict tsconfig, ESM-only

This is the recommended greenfield scaffold for a new TypeScript project in 2026.

## 1. Lint + format with Biome v2

**Default choice: Biome.** One Rust binary, one config file, handles both linting and formatting, ~10-25x faster than ESLint, and as of v2 ("Biotype", March 2025) has type-aware lint rules without requiring the TypeScript compiler.

- Biome official — https://biomejs.dev/
- Biome v2 announcement, "Biotype" — https://biomejs.dev/blog/biome-v2/
- Migration guide from ESLint+Prettier — https://biomejs.dev/guides/migrate-eslint-prettier/

### Install + init

```bash
npm i -D --save-exact @biomejs/biome
npx biome init
```

Produces `biome.json`. A reasonable starting config:

```json
{
  "$schema": "https://biomejs.dev/schemas/2.3.0/schema.json",
  "organizeImports": { "enabled": true },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true,
      "correctness": { "noUnusedVariables": "error" },
      "style": { "useConst": "error", "useTemplate": "error" },
      "suspicious": { "noExplicitAny": "error" }
    }
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 100
  }
}
```

### Commands

```bash
npx biome check .           # lint + format + organize-imports, report only
npx biome check --write .   # same, auto-fix
npx biome format --write .  # format only
npx biome lint .            # lint only
```

### When ESLint is still the right call

Don't switch to Biome if you rely on:

- Custom ESLint rules specific to your project.
- Framework-specific rule sets Biome doesn't replicate yet (e.g. `eslint-plugin-react-hooks` — though Biome v2 covers more of this than v1).
- Exact Prettier output parity (Biome's formatting is near-identical but not byte-identical).

Otherwise, for a greenfield project, Biome wins on speed, DX, and config surface area. Sources:
- Econify, "Biome v2 and Type-Aware Linting Explained" — https://www.econify.com/news/the-loop-biome-v2-type-aware-linting-without-the-compiler
- PkgPulse, "Biome vs ESLint + Prettier: Is the All-in-One Linter Ready?" — https://www.pkgpulse.com/blog/biome-vs-eslint-prettier-linting-2026

## 2. Strict `tsconfig.json`

Minimum `compilerOptions` for a new project in 2026:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "lib": ["ES2022"],

    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,

    "verbatimModuleSyntax": true,
    "isolatedModules": true,

    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true,

    "declaration": true,
    "sourceMap": true,
    "outDir": "dist"
  },
  "include": ["src/**/*"]
}
```

Sources:
- TSConfig reference — https://www.typescriptlang.org/tsconfig/
- 2ality, "A guide to `tsconfig.json`" (2025) — https://2ality.com/2025/01/tsconfig-json.html
- Effective TypeScript, Item 2 "Know Which TypeScript Options You're Using" — https://effectivetypescript.com/

### What each non-default flag buys you

- **`noUncheckedIndexedAccess`** — `arr[i]` returns `T | undefined`. Forces you to handle the out-of-range case. https://www.typescriptlang.org/tsconfig/#noUncheckedIndexedAccess
- **`exactOptionalPropertyTypes`** — distinguishes "property absent" from "property present but `undefined`." Catches a whole class of API contract bugs. https://www.typescriptlang.org/tsconfig/#exactOptionalPropertyTypes
- **`verbatimModuleSyntax`** (TS 5.0+) — requires `import type` for type-only imports; prevents the compiler from silently eliding import side-effects. Mandatory under bundlers like esbuild/swc. https://www.typescriptlang.org/tsconfig/#verbatimModuleSyntax
- **`isolatedModules`** — each file can be transpiled independently (required for esbuild/swc/Vite). https://www.typescriptlang.org/tsconfig/#isolatedModules
- **`noImplicitOverride`** — requires `override` keyword when overriding a base-class method. https://www.typescriptlang.org/tsconfig/#noImplicitOverride

## 3. ESM-only (`"type": "module"`)

In 2026, greenfield Node / browser / Bun projects are ESM-only.

`package.json`:
```json
{
  "name": "my-pkg",
  "version": "0.1.0",
  "type": "module",
  "engines": { "node": ">=22" },
  "main": "./dist/index.js",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js"
    }
  }
}
```

Requirements:
- All relative imports include the `.js` extension: `import { x } from "./util.js";` (not `./util`). This applies even in `.ts` source files — TypeScript resolves `.js` to the sibling `.ts`. See https://www.typescriptlang.org/docs/handbook/modules/reference.html#node16-nodenext-1
- `tsconfig` uses `"module": "NodeNext"` and `"moduleResolution": "NodeNext"` (not `"node"`).
- Use `import.meta.url` / `import.meta.dirname` (Node 22+) instead of `__dirname` / `__filename`.

Sources:
- Sindre Sorhus, "Pure ESM package" (the canonical migration checklist) — https://gist.github.com/sindresorhus/a39789f98801d908bbc7ff3ecc99d99c
- 2ality, "Publishing ESM-based npm packages with TypeScript" (Feb 2025) — https://2ality.com/2025/02/typescript-esm-packages.html
- Node.js ESM docs — https://nodejs.org/api/esm.html

### When to keep CJS

- Publishing a library that must support Node versions <18 or consumers that refuse to migrate.
- Integrating with an old toolchain (Jest <29, older Babel setups).

In those cases, dual-publish via `exports` conditional entries — but don't go out of your way to support CJS in an *application* you control.

## 4. Package manager / runtime

- **Bun** or **pnpm** for new projects. npm is fine but slow. Yarn v1 is end-of-life; Yarn Berry (v4) is viable but has fewer tutorials/plugins than pnpm.
- **tsx** or **Bun** to run `.ts` directly in development (no build step). `tsx` wraps Node + esbuild; Bun runs TS natively.

## Common mistakes

```
// WRONG — ESLint + Prettier + 12 plugins for a new project
.eslintrc.json (150 lines)
.prettierrc
.eslintignore

// RIGHT — one file
biome.json
```

```jsonc
// WRONG tsconfig — only "strict"
{ "compilerOptions": { "strict": true } }

// RIGHT — also opt into noUncheckedIndexedAccess + exactOptionalPropertyTypes
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "verbatimModuleSyntax": true
  }
}
```

```ts
// WRONG — omitting .js on relative imports in ESM
import { thing } from "./util";

// RIGHT — .js extension required under NodeNext / ESM
import { thing } from "./util.js";
```
