// Botanical split-screen /login form.
//
// Left panel: dotted-paper background with the dirt. brand and a short
// italic subtitle. Pre-auth avoids grow/device status so the screen
// does not show stale operational values before the app has a session.
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
    <main className="grid h-screen grid-cols-1 bg-paper text-ink md:grid-cols-[1.05fr_1fr]">
      {/* Left panel — dotted paper with the brand + field notes. */}
      <section className="bg-dot-grid relative flex items-center justify-center border-r border-rule-strong bg-paper-2">
        <div className="w-90 bg-paper-2 p-8">
          <svg
            aria-hidden="true"
            viewBox="0 0 100 100"
            className="h-35 w-35 text-ink-2"
            fill="none"
            stroke="currentColor"
            strokeWidth="0.8"
            strokeLinecap="round"
          >
            <path d="M50 88 C50 55, 20 45, 14 20 C 40 22, 52 38, 50 88 Z" />
            <path d="M50 88 C50 55, 80 45, 86 20 C 60 22, 48 38, 50 88 Z" />
            <path d="M50 88 L50 30" />
            <path
              d="M50 60 L32 48 M50 55 L68 43 M50 45 L34 35 M50 40 L66 30"
              opacity="0.6"
            />
          </svg>
          <h1 className="mt-5 font-serif text-fs-72 font-medium italic leading-none tracking-tighter text-ink">
            dirt<span className="text-accent-magenta">.</span>
          </h1>
          <p className="mt-3.5 max-w-fieldnote-sub font-serif text-fs-15 italic leading-normal text-ink-2">
            really dig your hands in there,
            <br />
            feel it under your nails
          </p>
        </div>
      </section>

      {/* Right panel — sign in form. */}
      <section className="flex items-center justify-center bg-paper px-10 py-10">
        <form
          onSubmit={(event) => {
            void handleSubmit(event);
          }}
          noValidate
          className="flex w-95 flex-col gap-6"
          aria-describedby={invalid ? errorId : undefined}
        >
          <div className="flex flex-col gap-1">
            <h2 className="font-sans text-fs-28 font-semibold tracking-tight text-ink">
              Sign in
            </h2>
            <p className="font-serif text-fs-15 italic text-ink-3">
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

          <label className="flex flex-col gap-1 font-mono text-fs-10 uppercase tracking-cap-field text-ink-3">
            username
            <input
              name="username"
              id="username"
              type="text"
              autoComplete="username"
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
              aria-invalid={invalid ? "true" : undefined}
              className="border border-rule-strong bg-paper px-3 py-2.5 font-mono text-fs-15 normal-case tracking-normal text-ink outline-none focus:border-ink"
            />
          </label>

          <label className="flex flex-col gap-1 font-mono text-fs-10 uppercase tracking-cap-field text-ink-3">
            password
            <input
              name="password"
              id="password"
              type="password"
              autoComplete="current-password"
              aria-invalid={invalid ? "true" : undefined}
              className="border border-rule-strong bg-paper px-3 py-2.5 font-mono text-fs-15 normal-case tracking-normal text-ink outline-none focus:border-ink"
            />
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="border border-ink bg-ink px-4 py-3 font-sans text-fs-13 font-semibold uppercase tracking-cap-short text-paper transition hover:bg-ink-2 disabled:opacity-60"
          >
            {submitting ? "Authenticating…" : "Enter the tent  →"}
          </button>
        </form>
      </section>
    </main>
  );
}
