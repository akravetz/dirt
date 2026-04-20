// web-ui/invariants/rules/_message.ts — HUMAN-OWNED
//
// Uniform failure-message template for custom ESLint rules in
// web-ui/invariants/rules/*. The Python analogue is
// apps/tests/invariants/_helpers.py:format_invariant_failure — agents
// learn the SMELL / WHY / FIX / Violations shape fast, and keeping the
// two languages aligned means zero context switching between a Python
// invariant failure and a TS invariant failure.
//
// Usage (inside a rule module):
//
//   import { formatInvariantMessage } from "./_message.ts";
//   ...
//   context.report({
//     node,
//     message: formatInvariantMessage({
//       smell: "Internal Test Mock",
//       why: "vi.mock() on '{{arg}}' targets an internal module — production code has no DI seam.",
//       fix: "Inject at parameter / context / provider; swap fake from tests.",
//       violations: [`vi.mock('${arg}')`],
//     }),
//     data: { arg },
//   });
//
// NOTE: the `{{template}}` tokens are ESLint's own interpolation — the
// helper does NOT resolve them; it just stitches the section headers.
// You still pass `data: {...}` in context.report. For rules that want
// the simpler single-line `WHY: ... FIX: ...` shape (matching the
// eslint-builtin rule messages from TS-03/05/09/10/etc.), use
// `formatShortInvariantMessage()`.

export interface InvariantMessageParts {
  /** Short SnakeCase-ish noun phrase. Example: "Broken Invariant Wiring". */
  smell: string;
  /** One-sentence reason the pattern is forbidden. */
  why: string;
  /** One-sentence corrective action. */
  fix: string;
  /** Optional list of concrete offending tokens / paths. */
  violations?: readonly string[];
}

export function formatInvariantMessage(parts: InvariantMessageParts): string {
  const lines: string[] = [
    `SMELL: ${parts.smell}`,
    `WHY: ${parts.why}`,
    `FIX: ${parts.fix}`,
  ];
  if (parts.violations && parts.violations.length > 0) {
    lines.push("Violations:");
    for (const v of parts.violations) {
      lines.push(`  - ${v}`);
    }
  }
  return lines.join("\n");
}

export interface ShortInvariantMessageParts {
  why: string;
  fix: string;
}

export function formatShortInvariantMessage(
  parts: ShortInvariantMessageParts,
): string {
  return `WHY: ${parts.why} FIX: ${parts.fix}`;
}
