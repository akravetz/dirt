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

const config: Linter.Config[] = [
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
    },
    settings: {
      "boundaries/elements": ELEMENT_TYPES,
      "boundaries/include": ["src/**/*.ts", "src/**/*.tsx"],
    },
    rules: {
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
    },
  },
];

export default config;
