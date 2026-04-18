---
title: No `namespace`, no class-heavy designs; ES modules + functions
concept: modern-idiomatic-typescript
updated: 2026-04-17
source: https://typescript-eslint.io/rules/no-namespace/
---

> This file anchors agents to current TypeScript practice. Prefer what's written here over training-data recollection — training-data TypeScript is heavy on `namespace`, `module { }` blocks, and class-per-file designs imported from C#/Java. Modern idiomatic TypeScript uses ES modules and functions.

# No `namespace`, no class-heavy designs

## Rule 1: Do not use `namespace` (or the old `module Foo { }` syntax) for application code

`namespace` is a pre-ES-modules TypeScript construct. Every modern JS/TS build tool (tsc with `--module`, esbuild, swc, Biome, webpack, Vite) assumes ES modules. `namespace` predates this and is now a code smell.

**`typescript-eslint`'s `plugin:@typescript-eslint/recommended` config enables `no-namespace` by default.** Source: https://typescript-eslint.io/rules/no-namespace/

Rationale from that page: *"Namespaces are an outdated way to organize TypeScript code, and ES2015 module syntax is now preferred (import/export)."*

TypeScript's own handbook concurs: *"You shouldn't try to namespace your module contents. The module file itself is already a logical grouping, and its top-level name is defined by the code that imports it."* Source: https://www.typescriptlang.org/docs/handbook/namespaces-and-modules.html

### Do / Don't

```ts
// WRONG
namespace MyLib {
  export function doThing() { /* ... */ }
  export interface Config { /* ... */ }
}
MyLib.doThing();

// RIGHT — one file, ES exports, normal imports
// my-lib.ts
export function doThing() { /* ... */ }
export interface Config { /* ... */ }

// caller.ts
import { doThing, type Config } from "./my-lib.js";
doThing();
```

### Narrow exception: `declare namespace` in `.d.ts`

Ambient declarations for legacy JS libraries that actually use global namespaces (e.g. old UMD bundles) can still use `namespace`. The ESLint rule's default `allowDefinitionFiles: true` permits this. For application `.ts` / `.tsx`: don't.

## Rule 2: Classes are an opt-in, not the default

TypeScript training data is saturated with Java/C#-flavored class-per-service designs (`UserService`, `LoggerFactory`, `Repository<T>` base classes). Modern TS/JS idiomatic code uses **functions and modules** as the default unit of code; classes exist for a specific purpose: encapsulating stateful behavior with a lifecycle.

**Default to a module with exported functions.** Reach for a class only when:

1. You have **non-trivial internal state** with invariants that must be maintained across method calls (e.g. a parser building up a tree, a connection pool).
2. You need **multiple instances** with independent state.
3. You're **implementing an interface contract** where instance-based dispatch is genuinely useful (e.g. a plugin architecture, a Stream subclass).

Do NOT use a class when:

- All methods are static (it's just a namespace — use a module).
- The "class" holds only data (use a plain object / record / discriminated union).
- You're reaching for `new FooService()` in a DI container out of habit.

### Do / Don't

```ts
// WRONG — class-as-namespace
class MathUtils {
  static add(a: number, b: number) { return a + b; }
  static multiply(a: number, b: number) { return a * b; }
}
MathUtils.add(1, 2);

// RIGHT — module with functions
// math-utils.ts
export function add(a: number, b: number) { return a + b; }
export function multiply(a: number, b: number) { return a * b; }

// caller
import * as math from "./math-utils.js";
math.add(1, 2);
```

```ts
// WRONG — class holding only data
class User {
  constructor(public id: string, public email: string) {}
}

// RIGHT — plain type
type User = { id: string; email: string };
```

Rationale: function-first designs compose better, tree-shake cleanly, are easier to test (no mocking `new`), and align with how modern React/Solid/Vue are written. Sources:
- React docs recommending function components over class components — https://react.dev/reference/react/Component ("Class components are still supported by React, but we don't recommend using them in new code.")
- LogRocket, "React Design Patterns and Best Practices" on the shift from class to function — https://blog.logrocket.com/react-typescript-10-patterns-writing-better-code/
- matklad, "TypeScript is Surprisingly OK for Compilers" — uses functional, module-level style throughout: https://matklad.github.io/2023/08/17/typescript-is-surprisingly-ok-for-compilers.html

## Rule 3: Prefer `type` over `interface` by default

This is opinionated, but there's a clear best-answer for greenfield code:

- **Use `type`** for everything by default.
- **Use `interface`** only when you need declaration merging (rare) or are authoring a library where consumers should `extends` your type.

Rationale: `type` can express every shape `interface` can, plus unions, intersections, mapped types, conditional types, and tuples. `interface` silently declaration-merges same-name declarations in the same scope — a real source of bugs in large codebases.

Matt Pocock: *"I agree [with the TS team's 'default to interface' guidance], except that declaration merging should feel scary enough for you to default to 'type'."* Source: https://x.com/mattpocockuk/status/1685947322491154433 and https://www.totaltypescript.com/type-vs-interface-which-should-you-use

### Do / Don't

```ts
// Fine either way for a plain object shape:
type User = { id: string; email: string };
interface User { id: string; email: string }

// `type` is the only option for these:
type Id = string | number;              // union
type ReadonlyUser = Readonly<User>;     // mapped
type UserId = User["id"];               // indexed access
type Result<T> = T extends Error ? never : T; // conditional

// `interface` merges silently (footgun):
interface Config { port: number }
// ...somewhere else in the codebase:
interface Config { host: string }
// Config is now { port: number; host: string } — maybe not what you wanted
```

Pick one rule per project and enforce it. The *worst* state is mixing `type` and `interface` arbitrarily.

## Common mistakes

```ts
// WRONG — namespace for grouping
namespace Utils {
  export const PI = 3.14;
  export function square(x: number) { return x * x; }
}

// RIGHT — a module named utils.ts
export const PI = 3.14;
export function square(x: number) { return x * x; }
```

```ts
// WRONG — static-only class
class Logger {
  static info(msg: string) { console.log(msg); }
  static error(msg: string) { console.error(msg); }
}

// RIGHT — a module with exported functions (optionally a namespace-import alias)
export function info(msg: string) { console.log(msg); }
export function error(msg: string) { console.error(msg); }
// usage: import * as log from "./logger.js"; log.info("...");
```
