// Botanical split-screen /login form.
//
// Left panel: dotted-paper background with the dirt. brand, a short
// italic subtitle, and a field-notes block listing GROW / DAY / PLANTS
// / LOC / AGENT. The field-notes block is deliberately hardcoded copy —
// no /api/grow/current call from this pre-auth screen per the plan.
//
// Right panel: "Sign in" heading + native <form> with username +
// password + a primary submit button. The ui/ layer is pure
// presentation (boundaries forbid ui → api-client); the actual POST is
// handled by the parent route via the `onSubmit` prop. On success the
// route navigates; on failure it passes an `error` string back in and
// this component flips aria-invalid + renders a <div role="alert">.
// No sr-only mirror structures, no custom test-only hooks.
import type { FormEvent } from "react";
import { useState } from "react";

interface LoginScreenProps {
  /**
   * Returns an error message string to render inline, or null on
   * success (the parent typically navigates before this resolves).
   */
  onSubmit: (creds: { username: string; password: string }) => Promise<string | null>;
}

// Field-notes copy mirrors the mockup (docs/plans/refs/login.png). Kept
// as a const table so swapping values for a demo or pre-launch flag is
// a one-line edit, and so the acceptance script's case-insensitive
// token scan (grow / day / plants / loc / agent) stays satisfied.
const FIELD_NOTES = [
  { label: "GROW", value: "Sirius Black × BS01" },
  { label: "DAY", value: "29 · flower wk 2" },
  { label: "PLANTS", value: "A · B · C · D" },
  { label: "LOC", value: "Denver, MT · closet tent" },
  { label: "AGENT", value: "Claudia · listening" },
] as const;

export function LoginScreen({ onSubmit }: LoginScreenProps) {
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Uncontrolled form: values live in the DOM, we read them from
  // FormData on submit. This is deliberate — a controlled-input
  // implementation misses .value= writes dispatched by automation
  // (Playwright, the agent-browser acceptance script) because React
  // overrides the input's native value setter. Uncontrolled inputs
  // play nicely with both human typing and synthetic .value + input
  // events, without the `Object.getOwnPropertyDescriptor` dance.
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const username = String(data.get("username") ?? "");
    const password = String(data.get("password") ?? "");
    setSubmitting(true);
    setError(null);
    const err = await onSubmit({ username, password });
    if (err !== null) {
      setError(err);
      setSubmitting(false);
    }
    // On success the route should navigate; leave the button disabled
    // so no stray second submit races the navigation.
  };

  const invalid = error !== null;
  const errorId = "login-error";

  return (
    <main className="grid min-h-screen grid-cols-1 bg-paper text-ink md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      {/* Left panel — dotted paper with the brand + field notes. */}
      <section className="bg-dot-grid relative flex flex-col justify-between gap-12 px-12 py-16">
        <div className="flex flex-col gap-8">
          <svg
            aria-hidden="true"
            viewBox="0 0 120 160"
            className="h-28 w-24 text-ink"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M60 150 V80" />
            <path d="M60 110 C 30 100, 18 70, 30 40 C 50 60, 60 80, 60 110 Z" />
            <path d="M60 110 C 90 100, 102 70, 90 40 C 70 60, 60 80, 60 110 Z" />
          </svg>
          <div>
            <h1 className="font-serif text-7xl italic leading-none text-ink">
              dirt<span className="text-accent-magenta">.</span>
            </h1>
            <p className="mt-6 max-w-xs font-serif text-lg italic text-ink-2">
              really dig your hands in there,
              <br />
              feel it under your nails
            </p>
          </div>
        </div>
        <dl className="flex flex-col gap-2 border-t border-rule pt-6 font-mono text-xs text-ink">
          {FIELD_NOTES.map(({ label, value }) => (
            <div key={label} className="flex gap-6">
              <dt className="w-20 uppercase tracking-caps text-ink-3">{label}</dt>
              <dd className="text-ink">{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* Right panel — sign in form. */}
      <section className="flex items-center justify-center bg-paper px-12 py-16">
        <form
          onSubmit={(event) => {
            void handleSubmit(event);
          }}
          noValidate
          className="flex w-full max-w-sm flex-col gap-6"
          aria-describedby={invalid ? errorId : undefined}
        >
          <div className="flex flex-col gap-2">
            <h2 className="font-serif text-4xl text-ink">Sign in</h2>
            <p className="font-serif text-base italic text-ink-2">
              Operator access only. This instrument talks back.
            </p>
          </div>

          {invalid ? (
            <div
              id={errorId}
              role="alert"
              className="border border-accent-magenta px-3 py-2 font-mono text-xs uppercase tracking-caps text-accent-magenta"
            >
              {error}
            </div>
          ) : null}

          <label className="flex flex-col gap-1 font-mono text-xs uppercase tracking-caps text-ink-3">
            Username
            <input
              name="username"
              id="username"
              type="text"
              autoComplete="username"
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
              aria-invalid={invalid ? "true" : undefined}
              className="border border-rule bg-paper px-3 py-2 font-mono text-sm normal-case tracking-normal text-ink outline-none focus:border-ink"
            />
          </label>

          <label className="flex flex-col gap-1 font-mono text-xs uppercase tracking-caps text-ink-3">
            Password
            <input
              name="password"
              id="password"
              type="password"
              autoComplete="current-password"
              aria-invalid={invalid ? "true" : undefined}
              className="border border-rule bg-paper px-3 py-2 font-mono text-sm normal-case tracking-normal text-ink outline-none focus:border-ink"
            />
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="bg-ink px-4 py-3 font-mono text-xs uppercase tracking-caps text-paper hover:bg-ink-2 disabled:opacity-60"
          >
            {submitting ? "Signing in…" : "Enter the tent →"}
          </button>
        </form>
      </section>
    </main>
  );
}
