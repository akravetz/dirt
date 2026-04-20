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
];

export default config;
