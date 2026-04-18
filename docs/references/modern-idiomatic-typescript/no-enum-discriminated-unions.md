---
title: Discriminated unions and `as const` objects over `enum`
concept: modern-idiomatic-typescript
updated: 2026-04-17
source: https://www.totaltypescript.com/four-essential-typescript-patterns
---

> This file anchors agents to current TypeScript practice. Prefer what's written here over training-data recollection — training data reaches for `enum` reflexively; modern idiomatic TypeScript does not.

# Discriminated unions and `as const` objects over `enum`

**Default rule: do not write `enum`.** Use a string literal union for simple sets, an `as const` object for enum-like constant groups, and a discriminated union for state machines / message types / action kinds.

## Why `enum` is out

`enum` emits an IIFE at runtime (so it's not zero-cost), has confusing numeric/string-enum dual behavior, breaks `isolatedModules` / `erasableSyntaxOnly` (TS 5.8+), and interacts badly with module transpilers (esbuild, swc) that don't implement full TS semantics.

- Total TypeScript, "Enums considered harmful" — https://www.youtube.com/watch?v=jjMbPt_H3RQ (Matt Pocock summarizes the case) and https://x.com/mattpocockuk/status/1598708710523772929
- 2ality, "TypeScript enums: use cases and alternatives" — https://2ality.com/2025/01/typescript-enum-patterns.html ("For most use cases, an enum is overkill. Use object literals with `as const`.")
- 2ality, "Alternatives to enums in TypeScript" (foundational) — https://2ality.com/2020/02/enum-alternatives-typescript.html

## The three replacements

### 1. String literal union (for simple label sets)

```ts
// Good
type LogLevel = "debug" | "info" | "warn" | "error";

function log(level: LogLevel, msg: string) { /* ... */ }

log("debug", "starting up");
log("fatal", "nope"); // type error — not in union

// Bad
enum LogLevel { Debug, Info, Warn, Error }
log(LogLevel.Debug, "starting up");
```

### 2. `as const` object (for enum-like constant groups)

Use when you want a runtime object *and* a type, or when you want `Object.values()` iteration.

```ts
// Good
export const LOG_LEVEL = {
  DEBUG: "debug",
  INFO: "info",
  WARN: "warn",
  ERROR: "error",
} as const;

export type LogLevel = (typeof LOG_LEVEL)[keyof typeof LOG_LEVEL];
// LogLevel = "debug" | "info" | "warn" | "error"

// Iterable at runtime:
for (const level of Object.values(LOG_LEVEL)) { /* ... */ }
```

Matt Pocock's preferred pattern. Source: https://x.com/mattpocockuk/status/1598708710523772929 and https://www.totaltypescript.com/how-to-use-satisfies-operator

Can combine with `satisfies` to enforce a shape:

```ts
const LOG_LEVEL = {
  DEBUG: "debug",
  INFO: "info",
} as const satisfies Record<string, string>;
```

### 3. Discriminated union (for variant types / state machines)

When each case carries **different data**, a discriminated union gives exhaustiveness checking and per-variant typing that `enum` cannot match.

```ts
// Good — every variant has its own payload shape
type Result<T> =
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: Error };

function render<T>(r: Result<T>) {
  switch (r.status) {
    case "loading": return "...";
    case "success": return JSON.stringify(r.data);   // data is T here
    case "error":   return r.error.message;          // error is Error here
    // no default needed — TS proves exhaustive
  }
}
```

Exhaustiveness: assign the scrutinee to `never` in the default branch to force the compiler to error when a new variant is added:

```ts
function assertNever(x: never): never {
  throw new Error(`Unhandled variant: ${JSON.stringify(x)}`);
}

switch (r.status) {
  case "loading": return "...";
  case "success": return "...";
  case "error":   return "...";
  default: return assertNever(r);
}
```

Sources:
- TypeScript handbook, "Narrowing > Discriminated unions" — https://www.typescriptlang.org/docs/handbook/2/narrowing.html#discriminated-unions
- Effective TypeScript, Item 28 "Prefer Types That Always Represent Valid States" (2nd ed.) — https://effectivetypescript.com/
- 2ality, "Alternatives to enums" — https://2ality.com/2020/02/enum-alternatives-typescript.html (discriminated unions as the rich alternative)

## Common mistakes

```ts
// WRONG — numeric enum
enum Status { Pending, Active, Archived }

// RIGHT
const STATUS = { PENDING: "pending", ACTIVE: "active", ARCHIVED: "archived" } as const;
type Status = (typeof STATUS)[keyof typeof STATUS];
```

```ts
// WRONG — booleans + parallel enum for "mode"
interface State { isLoading: boolean; isError: boolean; data?: User; error?: Error }

// RIGHT — make invalid states unrepresentable
type State =
  | { status: "loading" }
  | { status: "success"; data: User }
  | { status: "error"; error: Error };
```

Effective TypeScript, Item 28: "Valid states in the shape of your types keep many bugs at bay." Source: https://effectivetypescript.com/

## When `enum` is (barely) OK

- Interop with a generated `.d.ts` from a third-party API that uses `enum`.
- Shared constants between TS and emitted JS consumed by non-TS tooling, where you specifically want the runtime object semantics and can't use `as const`.

If you must use one, use **`const enum`** only if `isolatedModules` is off (it's incompatible), or prefer a string enum over a numeric enum. But in greenfield code: don't.
