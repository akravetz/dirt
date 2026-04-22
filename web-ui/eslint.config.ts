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
];

export default config;
