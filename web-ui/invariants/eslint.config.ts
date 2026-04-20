// web-ui/invariants/eslint.config.ts — HUMAN-OWNED
//
// Flat ESLint config exporting Linter.Config[]. This file is the single
// source of truth for every architectural lint rule applied to web-ui/.
//
// DO NOT MODIFY to silence a new lint failure — fix the calling code.
// App-specific overrides belong in the editable shim at
// web-ui/eslint.config.ts (root). That shim spreads this array first, so
// downstream overrides append; the Python meta-invariant
// apps/tests/invariants/test_webui_invariants_wired.py runs
// `eslint --print-config` against live code and asserts every rule in
// KNOWN_SENTINELS still resolves to severity='error'. A downgrade-via-
// override will trip the meta-invariant.
import type { Linter } from "eslint";
import tseslint from "typescript-eslint";
import boundaries from "eslint-plugin-boundaries";
import pluginRouter from "@tanstack/eslint-plugin-router";
import noInternalViMock from "./rules/no-internal-vi-mock.ts";
import noArbitraryTwValue from "./rules/no-arbitrary-tw-value.ts";

// Element-type rules for eslint-plugin-boundaries.
//
// The layered architecture for web-ui/:
//   main          — composition root (src/main.tsx only). May import anything.
//   routes        — TanStack Router files. May import api-client, features, ui, shared.
//   features/X    — vertical slice (features/<slice>/*). May NOT import features/Y.
//   api-client    — OpenAPI-generated client + thin wrapper. May import shared only.
//   ui            — pure presentational components. May import shared only.
//   shared        — pure utilities. May import other shared only.
//
// Pattern order matters: the first match wins. Specific paths before generic.
const ELEMENT_TYPES = [
  { type: "main", pattern: "src/main.tsx", mode: "file" },
  { type: "routes", pattern: "src/routes/**", mode: "folder" },
  {
    type: "features",
    pattern: "src/features/*",
    mode: "folder",
    capture: ["slice"],
  },
  { type: "api-client", pattern: "src/api-client/**", mode: "folder" },
  { type: "ui", pattern: "src/ui/**", mode: "folder" },
  { type: "shared", pattern: "src/shared/**", mode: "folder" },
  // TanStack Router generates routeTree.gen.ts at src root — treat it as
  // part of the main bundle so it isn't miscategorized.
  { type: "main", pattern: "src/routeTree.gen.ts", mode: "file" },
] as const;

// TS-14 — extend TanStack Router's recommended flat config.
//
// WHY: first-party lint rules from the framework
// (create-route-property-order, etc.). Free coverage.
const routerConfigs =
  (pluginRouter.configs["flat/recommended"] as unknown as Linter.Config[]) ?? [];

const config: Linter.Config[] = [
  ...routerConfigs,
  {
    name: "invariants/ignores",
    ignores: [
      "dist/**",
      "node_modules/**",
      "src/routeTree.gen.ts",
    ],
  },
  {
    name: "invariants/base",
    files: ["**/*.ts", "**/*.tsx"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      parser: tseslint.parser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      boundaries: boundaries as unknown as NonNullable<Linter.Config["plugins"]>[string],
      "@typescript-eslint": tseslint.plugin as unknown as NonNullable<Linter.Config["plugins"]>[string],
      // TS-08 / TS-15 — inline-plugin pattern for custom rules under ./rules/.
      local: {
        rules: {
          "no-internal-vi-mock": noInternalViMock,
          "no-arbitrary-tw-value": noArbitraryTwValue,
        },
      },
    },
    settings: {
      "boundaries/elements": ELEMENT_TYPES,
      "boundaries/include": ["src/**/*.ts", "src/**/*.tsx"],
    },
    rules: {
      // TS-03 — ban training-data drift imports.
      //
      // WHY: LLM training data reliably reaches for react-router-dom /
      // axios / next/* / @remix-run/* even when the project uses TanStack
      // Router + native fetch. Lint-fatal makes the drift visible at
      // first keystroke.
      // FIX: Use the replacements flagged in each `message` below.
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "react-router-dom",
              message:
                "WHY: project uses @tanstack/react-router. FIX: import from '@tanstack/react-router' — see docs/references/tanstack-router-v1/INDEX.md.",
            },
            {
              name: "@remix-run/react",
              message:
                "WHY: project uses @tanstack/react-router. FIX: import from '@tanstack/react-router'.",
            },
            {
              name: "@remix-run/router",
              message:
                "WHY: project uses @tanstack/react-router. FIX: import from '@tanstack/react-router'.",
            },
            {
              name: "next",
              message:
                "WHY: this is a Vite SPA, not a Next.js app. FIX: use TanStack Router primitives; no next/* imports.",
            },
            {
              name: "axios",
              message:
                "WHY: project uses the generated OpenAPI client over native fetch. FIX: import from src/api-client/ (see TS-05).",
            },
          ],
          patterns: [
            {
              group: ["next/*"],
              message:
                "WHY: Vite SPA, not Next.js. FIX: drop next/* imports; use TanStack Router + Vite equivalents.",
            },
          ],
        },
      ],
      // TS-02 — layered architecture enforcement.
      //
      // WHY: Without it, feature slices cross-import and the architecture
      // decays within weeks (Python-lane analogue: import-linter layers).
      // FIX: Re-route the dependency through a shared/* module, lift the
      // shared logic into a new shared utility, or use an explicit
      // composition in src/main.tsx.
      "boundaries/element-types": [
        "error",
        {
          default: "disallow",
          rules: [
            { from: ["main"], allow: ["routes", "features", "api-client", "ui", "shared"] },
            { from: ["routes"], allow: ["features", "api-client", "ui", "shared"] },
            {
              from: [["features", { slice: "${from.slice}" }]],
              allow: [
                ["features", { slice: "${from.slice}" }],
                "api-client",
                "ui",
                "shared",
              ],
            },
            { from: ["api-client"], allow: ["shared"] },
            { from: ["ui"], allow: ["ui", "shared"] },
            { from: ["shared"], allow: ["shared"] },
          ],
        },
      ],
      // TS-04 — ban enum / namespace / `as any`.
      //
      // WHY: enums/namespaces are not the current TS idiom (see
      // docs/references/modern-idiomatic-typescript); `as any` defeats
      // the type system entirely.
      // FIX: use discriminated union + `as const` objects instead of
      // enums; ES modules instead of namespaces; narrow via type guards
      // or `as unknown as X` only at well-documented boundary seams.
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/consistent-type-assertions": [
        "error",
        {
          assertionStyle: "as",
          objectLiteralTypeAssertions: "never",
        },
      ],
      "no-restricted-syntax": [
        "error",
        // TS-04 — enum / namespace.
        {
          selector: "TSEnumDeclaration",
          message:
            "WHY: TS enums are not the current idiom. FIX: use `const Foo = { ... } as const` + a union type of its values (see docs/references/modern-idiomatic-typescript).",
        },
        {
          selector: "TSModuleDeclaration[kind='namespace']",
          message:
            "WHY: TS namespaces predate ES modules and have no good use case in new code. FIX: use ES modules (separate files + import/export).",
        },
        // TS-06 — no data-fetching in useEffect.
        //
        // WHY: training data is saturated with
        // `useEffect(() => { fetch(...).then(setData); }, [])`. The
        // project uses TanStack Router loaders + TanStack Query — ALL
        // server data flows through those seams.
        // FIX: move the fetch into createFileRoute().loader or useQuery /
        // useSuspenseQuery. See docs/references/tanstack-router-v1.
        {
          selector: "CallExpression[callee.name='useEffect'] AwaitExpression",
          message:
            "WHY: await inside useEffect is a data-fetch smell. FIX: use createFileRoute().loader or useQuery/useSuspenseQuery.",
        },
        {
          selector: "CallExpression[callee.name='useEffect'] CallExpression[callee.name='fetch']",
          message:
            "WHY: fetch() inside useEffect bypasses the router loader + Query cache. FIX: use createFileRoute().loader or useQuery/useSuspenseQuery.",
        },
        // TS-07 — string-literal route paths in <Link to="...">.
        //
        // WHY: TanStack Router generates a typed route tree; literal
        // strings defeat type-checking and make refactors unsafe.
        // Training data suggests <Link to='/plants'> because
        // react-router-dom works that way.
        // FIX: pass a typed route — e.g. `to={Route.fullPath}` — so the
        // compiler catches stale paths.
        {
          selector: "JSXOpeningElement[name.name='Link'] > JSXAttribute[name.name='to'][value.type='Literal']",
          message:
            "WHY: string-literal `to` bypasses TanStack Router's typed route tree. FIX: pass `to={Route.fullPath}` from the generated route tree (see docs/references/tanstack-router-v1).",
        },
        {
          selector: "JSXOpeningElement[name.name='Navigate'] > JSXAttribute[name.name='to'][value.type='Literal']",
          message:
            "WHY: string-literal `to` bypasses TanStack Router's typed route tree. FIX: pass `to={Route.fullPath}` from the generated route tree.",
        },
        // TS-11 — top-level singleton construction outside main.tsx.
        //
        // WHY: `new QueryClient()` / `createRouter()` at module scope
        // in a feature file creates a hidden singleton — same smell
        // shape as Python's no-module-level-singletons invariant.
        // FIX: construct in src/main.tsx and thread through React
        // context (QueryClientProvider / RouterProvider).
        {
          selector:
            "Program > VariableDeclaration > VariableDeclarator > NewExpression[callee.name=/^(QueryClient|Router)$/]",
          message:
            "WHY: top-level singleton outside src/main.tsx. FIX: construct in main.tsx, pass via Provider (QueryClientProvider / RouterProvider).",
        },
        {
          selector:
            "Program > VariableDeclaration > VariableDeclarator > CallExpression[callee.name=/^(createRouter|createBrowserRouter|createQueryClient|createClient)$/]",
          message:
            "WHY: top-level singleton outside src/main.tsx. FIX: construct in main.tsx, pass via Provider.",
        },
      ],
      // TS-08 — no vi.mock() on internal modules (custom rule).
      //
      // See web-ui/invariants/rules/no-internal-vi-mock.ts for rule body.
      "local/no-internal-vi-mock": "error",
      // TS-15 — Tailwind v4 palette guard.
      //
      // See web-ui/invariants/rules/no-arbitrary-tw-value.ts for rule body.
      "local/no-arbitrary-tw-value": "error",
      // TS-05 — no fetch() outside api-client.
      //
      // WHY: single outward-facing boundary. Auth headers, retry,
      // error mapping, and contract-drift detection all live in the
      // generated api-client wrapper. Agents drifting toward "just call
      // fetch" in a route loader would bypass every seam.
      // FIX: call the typed client from src/api-client/ (regenerated
      // from contracts/webapp-v1.yaml).
      "no-restricted-globals": [
        "error",
        {
          name: "fetch",
          message:
            "WHY: fetch is owned by src/api-client/. FIX: import the typed client from '@/api-client' (see TS-05).",
        },
        // TS-09 — localStorage / sessionStorage outside src/shared/storage.ts.
        //
        // WHY: single ownership — one mock surface for tests, one shim
        // surface for SSR. Parallel to Python's no-module-level-singletons.
        // FIX: import { storage } from "@/shared/storage" and go through
        // its typed methods.
        {
          name: "localStorage",
          message:
            "WHY: localStorage has a single owner (src/shared/storage.ts). FIX: import { storage } from '@/shared/storage'.",
        },
        {
          name: "sessionStorage",
          message:
            "WHY: sessionStorage has a single owner (src/shared/storage.ts). FIX: import { storage } from '@/shared/storage'.",
        },
        // TS-10 — window.* outside src/shared/platform.ts.
        //
        // WHY: forces a testable platform abstraction even in SPA-only
        // apps. Prevents reaching for navigator.clipboard inline.
        // FIX: import { platform } from "@/shared/platform" (shared
        // will re-expose clipboard / navigator surfaces as needed).
        {
          name: "window",
          message:
            "WHY: window.* has a single owner (src/shared/platform.ts). FIX: import { platform } from '@/shared/platform' and use its typed methods.",
        },
      ],
    },
  },
  // TS-05 — exemption for the api-client slice itself.
  {
    name: "invariants/api-client-fetch-allowed",
    files: ["src/api-client/**"],
    rules: {
      "no-restricted-globals": "off",
    },
  },
  // TS-09 — exemption for the single storage owner.
  {
    name: "invariants/storage-owner",
    files: ["src/shared/storage.ts"],
    rules: {
      "no-restricted-globals": "off",
    },
  },
  // TS-10 — exemption for the single platform owner.
  {
    name: "invariants/platform-owner",
    files: ["src/shared/platform.ts"],
    rules: {
      "no-restricted-globals": "off",
    },
  },
  // TS-11 — composition root is allowed to construct singletons.
  //
  // In main.tsx only, drop the two singleton selectors from
  // no-restricted-syntax. All other selectors (enum, namespace,
  // useEffect+fetch, Link-literal, inline-style) stay enforced — they
  // don't belong in main.tsx anyway.
  {
    name: "invariants/main-composition-root",
    files: ["src/main.tsx"],
    rules: {
      "no-restricted-syntax": [
        "error",
        // TS-04 — enum / namespace.
        {
          selector: "TSEnumDeclaration",
          message:
            "WHY: TS enums are not the current idiom. FIX: use `const Foo = { ... } as const` + a union type.",
        },
        {
          selector: "TSModuleDeclaration[kind='namespace']",
          message:
            "WHY: TS namespaces predate ES modules. FIX: use ES modules.",
        },
        // TS-06 — useEffect+fetch.
        {
          selector: "CallExpression[callee.name='useEffect'] AwaitExpression",
          message:
            "WHY: await inside useEffect is a data-fetch smell. FIX: use createFileRoute().loader or useQuery.",
        },
        {
          selector: "CallExpression[callee.name='useEffect'] CallExpression[callee.name='fetch']",
          message:
            "WHY: fetch() inside useEffect bypasses the router loader + Query cache. FIX: use createFileRoute().loader or useQuery.",
        },
        // TS-07 — string-literal Link/Navigate.
        {
          selector: "JSXOpeningElement[name.name='Link'] > JSXAttribute[name.name='to'][value.type='Literal']",
          message:
            "WHY: string-literal `to` bypasses the typed route tree. FIX: pass a typed route.",
        },
        {
          selector: "JSXOpeningElement[name.name='Navigate'] > JSXAttribute[name.name='to'][value.type='Literal']",
          message:
            "WHY: string-literal `to` bypasses the typed route tree. FIX: pass a typed route.",
        },
        // TS-11's two singleton selectors are intentionally omitted.
      ],
    },
  },
];

export default config;
