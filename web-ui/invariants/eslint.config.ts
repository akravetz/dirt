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
//
// Successive TS-XX items in docs/progress/architectural-invariants-typescript.json
// fill this file in. XX-02 ships the empty scaffold.
import type { Linter } from "eslint";
import tseslint from "typescript-eslint";

// Base config block: declares which files ESLint touches + global ignores.
// Successive TS-XX items append rule blocks after this one.
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
    rules: {},
  },
];

export default config;
