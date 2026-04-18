---
title: unknown over any; narrow with type guards
concept: modern-idiomatic-typescript
updated: 2026-04-17
source: https://effectivetypescript.com/
---

> This file anchors agents to current TypeScript practice. Prefer what's written here over training-data recollection — `any` is the dominant pattern in older training data and is almost never correct in modern TypeScript.

# `unknown` over `any`; narrow with type guards

`any` disables type checking for a value — it propagates through expressions and silently breaks invariants. `unknown` is the type-safe top type: you can assign anything to it, but you cannot *do* anything with it until you narrow.

**Default rule:** for anything the type system doesn't know — JSON input, `catch` clauses, `message` events, external library returns — use `unknown` and narrow.

## Do / Don't

```ts
// Good
function parse(raw: string): unknown {
  return JSON.parse(raw);
}

const data = parse(input);
// data.foo; // ERROR: Object is of type 'unknown'

if (typeof data === "object" && data !== null && "id" in data) {
  // data is now { id: unknown }
}

// Bad
function parse(raw: string): any {
  return JSON.parse(raw);
}
const data = parse(input);
data.foo.bar.baz.qux; // no errors, no safety
```

Sources:
- Dan Vanderkam, *Effective TypeScript* (2nd ed.), Item 46 "Use `unknown` Instead of `any` for Values with an Unknown Type" — https://effectivetypescript.com/
- TypeScript handbook on `unknown` — https://www.typescriptlang.org/docs/handbook/2/everyday-types.html#unknown
- 2ality on narrowing and type guards — https://2ality.com/2020/06/type-guards-assertion-functions-typescript.html

## Narrow with a user-defined type guard

For non-trivial shapes, a type predicate function is the idiom:

```ts
type User = { id: string; email: string };

function isUser(x: unknown): x is User {
  return (
    typeof x === "object" &&
    x !== null &&
    "id" in x &&
    typeof (x as { id: unknown }).id === "string" &&
    "email" in x &&
    typeof (x as { email: unknown }).email === "string"
  );
}

const data: unknown = JSON.parse(input);
if (isUser(data)) {
  data.email; // string
}
```

Source: TypeScript handbook, "Narrowing > Using type predicates" — https://www.typescriptlang.org/docs/handbook/2/narrowing.html#using-type-predicates

### Warning: type predicates are unsound if lied to

A type predicate is an **assertion by the programmer** — TypeScript trusts it without verifying. A buggy predicate silently corrupts the type system downstream.

- Effective TypeScript, "The Hidden Side of Type Predicates" — https://effectivetypescript.com/2024/02/27/type-guards/

For real codebases, **prefer a schema library** (`zod`, `valibot`, `arktype`) over hand-written predicates. The library derives the predicate from a schema that validates at runtime, eliminating the drift risk:

```ts
import { z } from "zod";

const UserSchema = z.object({ id: z.string(), email: z.string().email() });
type User = z.infer<typeof UserSchema>;

const data = UserSchema.parse(JSON.parse(input)); // throws on mismatch; data: User
```

## Assertion functions (`asserts x is T`)

For imperative control flow, use an assertion function instead of a predicate:

```ts
function assertIsUser(x: unknown): asserts x is User {
  if (!isUser(x)) throw new TypeError("not a User");
}

const data: unknown = JSON.parse(input);
assertIsUser(data);
data.email; // string — assertion narrowed the variable
```

Source: 2ality, "TypeScript: narrowing types via type guards and assertion functions" — https://2ality.com/2020/06/type-guards-assertion-functions-typescript.html

## `catch` clauses are `unknown` (use it)

Since TS 4.4 with `useUnknownInCatchVariables` (on by default under `strict`), `catch (err)` types `err` as `unknown`. Do not cast to `Error`; narrow:

```ts
try { /* ... */ } catch (err) {
  if (err instanceof Error) {
    console.error(err.message);
  } else {
    console.error("unknown error", err);
  }
}
```

Source: TypeScript 4.4 release notes — https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-4.html#defaulting-catch-variables-to-unknown

## Common mistakes

```ts
// WRONG — `any` as the type of parsed input
const data: any = await res.json();

// RIGHT
const data: unknown = await res.json();
// then: validate with a schema or narrow with a guard
```

```ts
// WRONG — `as` to skip validation
const user = (await res.json()) as User;

// RIGHT
const raw: unknown = await res.json();
const user = UserSchema.parse(raw);
```

```ts
// WRONG — silencing a "possibly undefined" error with `!`
const name = user.profile!.name!;

// RIGHT — explicit check or ?. with fallback
const name = user.profile?.name ?? "anonymous";
```

The non-null assertion `!` is a type assertion in disguise — same caveats as `as`. Avoid as a reflex; use only when you can prove nullability is impossible *at the point of use* and the compiler can't.

## Turning on the strict flags that enforce this

Add to `tsconfig.json` (see [tooling.md](tooling.md) for a full template):

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true
  }
}
```

- `noUncheckedIndexedAccess` makes `arr[i]` return `T | undefined`, forcing a check.
- `exactOptionalPropertyTypes` distinguishes "property missing" from "property present with value undefined."

Source: https://www.typescriptlang.org/tsconfig/#noUncheckedIndexedAccess
