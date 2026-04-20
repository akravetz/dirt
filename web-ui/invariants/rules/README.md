# web-ui/invariants/rules/ — custom ESLint rules

Custom rules live here as TypeScript source. They are registered via
flat-config's inline-plugin pattern in `../eslint.config.ts`:

```ts
import noInternalViMock from "./rules/no-internal-vi-mock.ts";
// ...
{
  plugins: { local: { rules: { "no-internal-vi-mock": noInternalViMock } } },
  rules: { "local/no-internal-vi-mock": "error" },
}
```

Every custom rule MUST:

1. Export a `Rule.RuleModule` (ESLint rule definition) as default.
2. Emit its `message` in the SMELL / WHY / FIX / Violations shape (see
   `_message.ts` when it lands in XX-01). Match the Python
   `format_invariant_failure` output so agents see one UX across languages.
3. Be deterministic (no fs / network in the rule body).
