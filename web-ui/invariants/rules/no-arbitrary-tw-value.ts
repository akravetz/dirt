// web-ui/invariants/rules/no-arbitrary-tw-value.ts — HUMAN-OWNED
//
// Flags Tailwind arbitrary-value utilities that sidestep the project
// palette: `bg-[#abc]`, `text-[14px]`, etc.
//
// WHY: docs/references/tailwind-v4/INDEX.md pins the project palette
// (paper/ink/magenta + Fraunces/IBM Plex Mono/Inter). Arbitrary values
// escape the design system and make visual drift invisible at review.
// FIX: use a palette class (bg-paper, text-ink) or add the missing
// token to styles.css `@theme` + `@utility`.
//
// Targets: JSX `className="..."` string literals and the string parts of
// template literals inside className. Not a perfect Tailwind parser —
// just a lint-rule-grade heuristic that catches the common smells.

import type { Rule } from "eslint";

// Matches arbitrary color: bg-[#..] / text-[#..] / border-[rgb( / etc.
const COLOR_ARBITRARY = /\b(?:bg|text|border|ring|fill|stroke|from|to|via)-\[(#|rgb|hsl)/;
// Matches arbitrary numeric size: w-[12px], p-[4rem], leading-[20px], …
const SIZE_ARBITRARY = /\b(?:w|h|p[xyltrb]?|m[xyltrb]?|gap|text|leading|tracking|rounded|size)-\[[-+\d]/;

function flag(context: Rule.RuleContext, node: Rule.Node, text: string): void {
  if (COLOR_ARBITRARY.test(text) || SIZE_ARBITRARY.test(text)) {
    context.report({
      node,
      messageId: "arbitrary",
      data: { text },
    });
  }
}

const rule: Rule.RuleModule = {
  meta: {
    type: "problem",
    docs: {
      description:
        "Forbid Tailwind arbitrary-value utilities that sidestep the project palette.",
    },
    schema: [],
    messages: {
      arbitrary:
        "WHY: arbitrary Tailwind value in `{{text}}` sidesteps the palette (paper/ink/magenta + typographic scale). FIX: use a palette class, or add the missing token to src/styles.css @theme / @utility (human review). See docs/references/tailwind-v4.",
    },
  },
  create(context) {
    return {
      JSXAttribute(node) {
        // @ts-expect-error — ESLint AST doesn't ship full JSX types
        if (node.name?.name !== "className" && node.name?.name !== "class") {
          return;
        }
        // @ts-expect-error — value is Literal | JSXExpressionContainer | null
        const value = node.value;
        if (!value) return;
        if (value.type === "Literal" && typeof value.value === "string") {
          flag(context, node as Rule.Node, value.value);
          return;
        }
        if (value.type === "JSXExpressionContainer") {
          const expr = value.expression;
          if (expr.type === "Literal" && typeof expr.value === "string") {
            flag(context, node as Rule.Node, expr.value);
            return;
          }
          if (expr.type === "TemplateLiteral") {
            for (const quasi of expr.quasis) {
              flag(context, node as Rule.Node, quasi.value.cooked ?? "");
            }
          }
        }
      },
    };
  },
};

export default rule;
