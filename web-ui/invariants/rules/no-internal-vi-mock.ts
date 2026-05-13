// web-ui/invariants/rules/no-internal-vi-mock.ts — HUMAN-OWNED
//
// Custom ESLint rule: forbids `vi.mock('<internal-module>')` calls.
//
// WHY: mocking an internal module signals that production code has no
// injection seam for the test. The Python-lane analogue is
// apps/tests/invariants/test_no_patching_production_code.py — same
// smell, same fix (inject at a boundary instead of monkey-patching).
//
// What counts as "internal":
//   - anything starting with "@/" (the TS path alias for src/)
//   - anything resolving to a relative path that stays inside src/
//
// Legitimate seams for test fakes (NOT flagged):
//   - API boundary fakes
//   - QueryClientProvider with a test QueryClient
//   - Context providers with fake implementations
//   - Component props that take a dependency
//
// FIX: lift the dependency out of the production module, inject it via
// parameter / context / provider, and swap in a fake from test code.
import type { Rule } from "eslint";
import { formatInvariantMessage } from "./_message.ts";

const MESSAGE = formatInvariantMessage({
  smell: "Internal Test Mock",
  why: "vi.mock('{{arg}}') targets an internal module — production code has no injection seam.",
  fix: "Lift the dependency to a parameter / context / provider; swap in a fake from test code. API boundary fakes are fine.",
  violations: ["vi.mock('{{arg}}')"],
});

const rule: Rule.RuleModule = {
  meta: {
    type: "problem",
    docs: {
      description:
        "Forbid vi.mock() on internal modules — indicates missing DI seam.",
    },
    schema: [],
    messages: {
      internalMock: MESSAGE,
    },
  },
  create(context) {
    return {
      CallExpression(node) {
        const { callee, arguments: args } = node;
        if (callee.type !== "MemberExpression") return;
        if (
          callee.object.type !== "Identifier" ||
          callee.object.name !== "vi"
        ) {
          return;
        }
        if (
          callee.property.type !== "Identifier" ||
          callee.property.name !== "mock"
        ) {
          return;
        }
        const [first] = args;
        if (!first || first.type !== "Literal") return;
        const value = first.value;
        if (typeof value !== "string") return;
        // "@/..." path-alias import.
        if (value.startsWith("@/")) {
          context.report({
            node,
            messageId: "internalMock",
            data: { arg: value },
          });
          return;
        }
        // Relative import whose prefix is ./ or ../ — treat as internal.
        // We can't fully resolve without the TS config, but anything
        // relative is by definition inside the project tree.
        if (value.startsWith("./") || value.startsWith("../")) {
          context.report({
            node,
            messageId: "internalMock",
            data: { arg: value },
          });
        }
      },
    };
  },
};

export default rule;
