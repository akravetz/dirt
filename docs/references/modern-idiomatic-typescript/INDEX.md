---
title: Modern Idiomatic TypeScript Reference Pack
concept: modern-idiomatic-typescript
mode: idioms
version: TypeScript 5.x (through 5.7), Biome 2.x
updated: 2026-04-17
---

# Modern Idiomatic TypeScript

This pack encodes current (2025-2026) idiomatic TypeScript for greenfield and actively-maintained codebases. It is **prescriptive, not descriptive** — pick the lane the pack picks unless you have a concrete reason to deviate. Sources are cited at point-of-use in every topic file.

Training data is heavily weighted toward 2018-2021 TypeScript patterns: `enum`, `namespace`, class-heavy designs, `any` casts, `as` assertions, ESLint+Prettier configs with dozens of plugins. Those patterns are no longer idiomatic. This pack is the override.

## When to consult this pack

Read this INDEX first, then pull the relevant topic file(s), before:

- Writing **any new `.ts` / `.tsx` file** in the project
- Refactoring existing TypeScript
- Choosing types for a public API (exported functions, React props, SDK surfaces)
- Picking lint/format tooling or editing `tsconfig.json` / `biome.json`
- Declaring enum-like sets of constants, error kinds, action types, route maps, or any discriminated state
- Handling untrusted input (API responses, `JSON.parse`, `message` events, `localStorage`)

Prefer what's in this pack over recollection — LLM training data lags current TypeScript practice by several years.

## Topics

- **[Prefer `satisfies` over type assertions](satisfies-over-assertions.md)** — When you want inference of the literal type *and* shape-checking. Read before annotating any object/array literal constant.
- **[Discriminated unions and `as const` objects over `enum`](no-enum-discriminated-unions.md)** — How to model enum-like data without emitting runtime `enum` IIFEs. Read before writing any `enum`.
- **[`unknown` over `any`; narrow with type guards](unknown-over-any.md)** — The `any` escape hatch is almost never correct in 2026. Read before touching external input, `JSON.parse`, or fetch responses.
- **[Branded types for nominal IDs and validated strings](branded-types.md)** — How to make `UserId` and `Email` non-interchangeable with plain `string`. Read when modeling IDs, tokens, or post-validation values.
- **[No `namespace`, no `module` keyword, no class-heavy designs](no-namespace-no-classes.md)** — Use ES modules and functions. Read before typing the word `namespace` or reaching for class-based dependency-injection.
- **[Tooling: Biome over ESLint+Prettier, strict `tsconfig.json`, ESM-only](tooling.md)** — Greenfield project scaffolding. Read before adding lint/format tooling or writing a `tsconfig.json`.

## Version-specific warnings

Training-data defaults that this pack overrides:

- **`enum Foo { ... }`** — emits runtime IIFE and pollutes bundle. Use `as const` objects + discriminated unions. See [no-enum-discriminated-unions.md](no-enum-discriminated-unions.md).
- **`namespace Foo { ... }`** — deprecated for application code; `typescript-eslint` flags it as `no-namespace` in the recommended config. Use ES modules. See [no-namespace-no-classes.md](no-namespace-no-classes.md).
- **`value as Type`** — silent cast, skips shape check. Use `satisfies` (for literals) or narrow via type guard (for unknown input). See [satisfies-over-assertions.md](satisfies-over-assertions.md) and [unknown-over-any.md](unknown-over-any.md).
- **`any`** — defeats type-checking entirely. Use `unknown` and narrow. See [unknown-over-any.md](unknown-over-any.md).
- **`class FooService { ... }` holding plain data / static methods** — prefer functions and module-scoped state. Classes are fine for *stateful* abstractions with lifecycle; they are not the default unit of code. See [no-namespace-no-classes.md](no-namespace-no-classes.md).
- **ESLint + Prettier + `@typescript-eslint` + 14 plugins** — Biome v2 replaces all of this for greenfield projects with one Rust binary and ~10-25x faster runs. See [tooling.md](tooling.md).
- **`type Id = string`** for IDs — every string is assignable to it, offering no safety. Use branded types. See [branded-types.md](branded-types.md).
- **`interface` used for React prop types out of habit** — declaration merging hazard; prefer `type` unless you need extension. See [no-namespace-no-classes.md](no-namespace-no-classes.md) ("type vs interface" section).
- **`tsconfig.json` with just `"strict": true`** — miss `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`. See [tooling.md](tooling.md).

## Sources

Primary authoritative voices cited in this pack:

- Matt Pocock / Total TypeScript — https://www.totaltypescript.com/
- Dan Vanderkam / Effective TypeScript (2nd ed.) — https://effectivetypescript.com/
- Axel Rauschmayer / 2ality — https://2ality.com/
- Biome official docs — https://biomejs.dev/
- TypeScript official release notes — https://www.typescriptlang.org/docs/handbook/release-notes/
- typescript-eslint — https://typescript-eslint.io/

See individual topic files for the specific URL backing each prescription.
