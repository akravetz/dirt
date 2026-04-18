---
title: Branded types for nominal IDs and validated strings
concept: modern-idiomatic-typescript
updated: 2026-04-17
source: https://www.totaltypescript.com/workshops/advanced-typescript-patterns/branded-types/what-is-a-branded-type
---

> This file anchors agents to current TypeScript practice. Prefer what's written here over training-data recollection — branded types are absent from most older TypeScript content but are the idiomatic tool for IDs, tokens, and post-validation values.

# Branded types for nominal IDs and validated strings

TypeScript is **structurally typed** — two types with the same shape are interchangeable. That's the default, and usually what you want. But for IDs (`UserId` vs `OrderId`), validated values (`Email` vs `string`), and currency amounts (`Cents` vs `number`), structural typing is too loose: any random `string` or `number` is assignable, defeating the intent.

**Use a branded type to simulate nominal typing for these cases.**

## The pattern

```ts
// Define a brand helper once, export from a shared module:
declare const brand: unique symbol;
export type Brand<T, B> = T & { readonly [brand]: B };

// Use it:
export type UserId  = Brand<string, "UserId">;
export type OrderId = Brand<string, "OrderId">;
export type Email   = Brand<string, "Email">;
export type Cents   = Brand<number, "Cents">;

// Now:
const u: UserId = "user_123";        // ERROR — string not assignable to UserId
const u: UserId = "user_123" as UserId; // OK but explicit (see below)

function getUser(id: UserId) { /* ... */ }
function getOrder(id: OrderId) { /* ... */ }

declare const uid: UserId;
declare const oid: OrderId;
getUser(oid); // ERROR — you cannot pass an OrderId where a UserId is expected
```

At **runtime** there is no brand — these types erase to `string` / `number`. Zero runtime cost.

Sources:
- Matt Pocock, "What is a Branded Type?" (Total TypeScript) — https://www.totaltypescript.com/workshops/advanced-typescript-patterns/branded-types/what-is-a-branded-type
- Matt Pocock, "Four Essential TypeScript Patterns" — https://www.totaltypescript.com/four-essential-typescript-patterns (branded types listed as one of the four)
- Dan Vanderkam, *Effective TypeScript* 2nd ed., Item 37 "Use Brands for Nominal Typing" — https://effectivetypescript.com/
- TypeScript Deep Dive on branded primitives — https://basarat.gitbook.io/typescript/main-1/nominaltyping

## Make a branded value: cast only at the validation boundary

The *only* place you should cast into a branded type is inside a validation / parsing function. Once validated, the branded value flows freely; nothing outside the validator can forge one.

```ts
export function parseEmail(raw: string): Email {
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(raw)) {
    throw new Error(`Invalid email: ${raw}`);
  }
  return raw as Email; // the one legitimate cast
}

// Better: integrate with your schema library
import { z } from "zod";

const EmailSchema = z.string().email().brand<"Email">();
type Email = z.infer<typeof EmailSchema>; // already branded

const email = EmailSchema.parse(input); // throws if invalid; Email type
```

Source: Matt Pocock, "Using Branded Types to Validate Code Logic" — https://www.totaltypescript.com/workshops/advanced-typescript-patterns/branded-types/creating-validation-boundaries-with-branded-types/solution

## When to brand

Brand when a primitive type carries a constraint that the compiler can't otherwise express:

- **IDs**: `UserId`, `OrderId`, `SessionId` — preventing cross-contamination.
- **Post-validation values**: `Email`, `Url`, `UUID`, `NonEmptyString`, `PositiveInt`.
- **Units**: `Cents` vs `Dollars`, `Meters` vs `Feet`, `Seconds` vs `Milliseconds` — famously the cause of the $125M Mars Climate Orbiter loss.
- **Security-sensitive wrappers**: `SqlSafeString`, `HtmlEscapedString`, `SanitizedFilename`.

## When NOT to brand

- A value used in only one function — the cost (indirection, casts) exceeds the benefit.
- You have a proper class or runtime wrapper already — use that, or brand *and* use it but don't duplicate effort.
- Prototyping — brands add friction. Add them when the domain stabilizes.

## Common mistakes

```ts
// WRONG — plain type aliases give zero safety
type UserId = string;
type OrderId = string;

function getUser(id: UserId) { /* ... */ }
declare const orderId: OrderId;
getUser(orderId); // compiles — string is string
```

```ts
// WRONG — branding but then casting everywhere
const id = someString as UserId; // at every call site

// RIGHT — cast only inside a factory/validator
function toUserId(raw: string): UserId {
  if (!/^user_[a-z0-9]+$/.test(raw)) throw new Error("bad id");
  return raw as UserId;
}
```

## Libraries that provide this out of the box

- Zod: `.brand<"Email">()` — https://zod.dev/
- Effect Schema: first-class branded types — https://effect.website/
- ts-brand, newtype-ts — dedicated brand-helper packages

Prefer a schema library over hand-rolled brands when you're already validating at the boundary; the schema defines the shape and the brand in one place.
