// web-ui/eslint.config.ts — EDITABLE SHIM
//
// This file is agent-editable. It spreads the HUMAN-OWNED invariants
// config from ./invariants/eslint.config.ts first, then allows
// app-specific overrides after — but severity downgrades on any rule in
// the meta-invariant's KNOWN_SENTINELS will trip
// apps/tests/invariants/test_webui_invariants_wired.py, which resolves
// `eslint --print-config` against the live tree.
//
// App-specific overrides pattern:
//   { files: ["src/new-feature/**"], rules: { ... } }
import type { Linter } from "eslint";
import invariants from "./invariants/eslint.config.ts";

const config: Linter.Config[] = [
  ...invariants,
  // App-specific overrides go below.
  //
  // MSW smoke tests under src/mocks/__tests__/ need raw `fetch` to
  // *prove* the worker intercepts the network layer. Running the call
  // through src/api-client/ would defeat the purpose: the api-client
  // only knows contract paths, but the smoke test hits a synthetic
  // /api/__smoke endpoint so it's independent of any real BE route.
  // Scope: test files under src/mocks/__tests__/ only.
  {
    name: "app/mocks-tests-raw-fetch",
    files: ["src/mocks/__tests__/*.ts", "src/mocks/__tests__/*.tsx"],
    rules: {
      "no-restricted-globals": "off",
    },
  },
  // Playwright e2e specs (tests/e2e/**) run inside the Playwright
  // Node-side test process, not inside the app bundle, and use
  // `page.addInitScript` to inject code that runs against the browser
  // `window` directly. TS-09 / TS-10's "single owner" wrappers are a
  // runtime-correctness invariant for app code, not test code —
  // routing addInitScript through shared/storage.ts would actually
  // defeat the purpose (the init script has to touch window.*
  // directly, before the app boots). Scope is narrow: tests/e2e/**.
  {
    name: "app/e2e-specs-raw-window",
    files: ["tests/e2e/**/*.ts", "tests/e2e/**/*.tsx"],
    rules: {
      "no-restricted-globals": "off",
    },
  },
];

export default config;
