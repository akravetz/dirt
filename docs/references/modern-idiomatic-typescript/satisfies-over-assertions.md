---
title: Prefer satisfies over type assertions
concept: modern-idiomatic-typescript
updated: 2026-04-17
source: https://www.totaltypescript.com/clarifying-the-satisfies-operator
---

> This file anchors agents to current TypeScript practice. Prefer what's written here over training-data recollection — training-data TypeScript predates the `satisfies` operator (added in TS 4.9, late 2022) and defaults to `as` assertions, which are unsafe.

# Prefer `satisfies` over type assertions

For typed object and array literals where you want (a) the precise literal types inferred and (b) the shape validated, use the `satisfies` operator. Do **not** reach for `as` or a variable-level type annotation as the default.

`satisfies` was introduced in TypeScript 4.9 and is now the canonical way to "type-check this literal without widening it." See https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-9.html#the-satisfies-operator.

## Do / Don't

```ts
type Routes = Record<string, `/${string}`>;

// Good — satisfies checks shape, preserves literal inference
const routes = {
  home: "/",
  about: "/about",
  blog: "/blog",
} satisfies Routes;

routes.home; // type is "/", not string

// Bad — variable annotation widens values to string
const routes: Routes = {
  home: "/",
  about: "/about",
};
routes.home; // type is string, literal info lost

// Bad — `as` is a cast. It will happily lie to the compiler.
const routes = {
  home: "/",
  about: "not-a-valid-path", // no error!
} as Routes;
```

Matt Pocock: "The satisfies operator lets us validate the type of an expression without changing the resulting type of that expression." Source: https://www.totaltypescript.com/clarifying-the-satisfies-operator

2ality (Axel Rauschmayer) reaches the same conclusion: use `satisfies` to validate the shape of an object literal without widening the inferred type. Source: https://2ality.com/2025/01/tsconfig-json.html (sidebar on `satisfies` in the modern TS config guide).

Dan Vanderkam, *Effective TypeScript* (2nd ed.), Item 32 "Prefer the `satisfies` Operator to Type Assertions" — covers the same prescription. Source: https://effectivetypescript.com/

## When `as` is actually correct

`as` is narrow-purpose. Acceptable uses:

1. **`as const`** — tells the compiler to infer the most literal / readonly type. This is a different operator in practice; it does not skip type-checking.
   ```ts
   const directions = ["north", "south", "east", "west"] as const;
   // inferred: readonly ["north", "south", "east", "west"]
   ```
2. **Narrowing a value when you have information the compiler doesn't**, with a comment explaining why. Rare; almost always a type guard is better.
3. **DOM APIs** where the type system is genuinely too loose (e.g. `event.target as HTMLInputElement`). Even here, prefer an `instanceof` check where possible.

If you find yourself writing `as SomeInterface` to silence an error, you are almost certainly papering over a real bug. Stop and ask whether a type guard (`x is T`) or `satisfies` would work.

## Common mistakes

Training-data patterns to override:

```ts
// WRONG — `as` pattern from pre-2023 TypeScript
const config = {
  port: 3000,
  host: "localhost",
} as Config;

// RIGHT
const config = {
  port: 3000,
  host: "localhost",
} satisfies Config;
```

```ts
// WRONG — unknown value cast to a specific type
const data = JSON.parse(input) as User;

// RIGHT — parse into unknown, then validate/narrow
const data: unknown = JSON.parse(input);
if (isUser(data)) {
  // data is User here
}
// or use a parser: zod, valibot, arktype
```

See [unknown-over-any.md](unknown-over-any.md) for the narrow-from-unknown pattern.

## Cross-references

- Pair `satisfies` with `const` type parameters (TS 5.0+) when writing generic identity functions. See https://devblogs.microsoft.com/typescript/announcing-typescript-5-0/#const-type-parameters.
- For tuple inference, `satisfies [number, number]` or `as const` both work; `as const` is tighter when you want `readonly`.
