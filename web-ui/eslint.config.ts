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

type RestrictedImportPath = {
  name: string;
  message: string;
};

type RestrictedImportsOptions = {
  paths?: RestrictedImportPath[];
  patterns?: unknown[];
};

type RestrictedImportsRule = ["error", RestrictedImportsOptions];

const legacyHostedCloudImportRestriction = {
  name: "@/api-client/cloud",
  message: "Use createHostedApiClient() and generated hosted schema types instead.",
} satisfies RestrictedImportPath;

function isRestrictedImportsRule(rule: unknown): rule is RestrictedImportsRule {
  return (
    Array.isArray(rule) &&
    rule[0] === "error" &&
    typeof rule[1] === "object" &&
    rule[1] !== null
  );
}

function withLegacyHostedCloudImportBan(config: Linter.Config): Linter.Config {
  const rule = config.rules?.["no-restricted-imports"];
  if (config.name !== "invariants/base" || !isRestrictedImportsRule(rule)) {
    return config;
  }

  const [, options] = rule;
  return {
    ...config,
    rules: {
      ...config.rules,
      "no-restricted-imports": [
        "error",
        {
          ...options,
          paths: [...(options.paths ?? []), legacyHostedCloudImportRestriction],
        },
      ],
    },
  };
}

const config: Linter.Config[] = [
  ...invariants.map(withLegacyHostedCloudImportBan),
  // App-specific overrides go below.
];

export default config;
