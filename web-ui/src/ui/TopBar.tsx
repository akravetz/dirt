import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { storage } from "@/shared/storage";

// Primary nav tabs. Paths match the file-based routes under src/routes/;
// `as const` preserves the literal union so `navigate({ to })` stays
// type-checked against the generated route tree.
const TABS = [
  { label: "Dashboard", path: "/" },
  { label: "Live", path: "/live" },
  { label: "Wiki", path: "/wiki" },
] as const;

const THEME_STORAGE_KEY = "dirt.theme";
type Theme = "light" | "dark";

function readStoredTheme(): Theme {
  const raw = storage.get(THEME_STORAGE_KEY);
  return raw === "dark" ? "dark" : "light";
}

interface TopBarProps {
  /**
   * Grow-context summary rendered beside the brand as
   * "Day {dayNumber} · {strain}". Sourced from GET /api/grow/current by
   * the root route (ui/ can't import api-client under TS-02). Omit
   * while the query is loading or on pre-auth screens that predate the
   * grow identity (the TopBar itself is already hidden on /login).
   */
  growContext?: { dayNumber: number; strain: string } | null;
}

export function TopBar({ growContext = null }: TopBarProps) {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [theme, setTheme] = useState<Theme>(readStoredTheme);

  // Apply the theme as a data attribute on <html> so Tailwind's
  // `@custom-variant dark` (configured in styles.css when needed) picks
  // it up, and persist the choice through the single storage owner.
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    storage.set(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  const nextTheme: Theme = theme === "dark" ? "light" : "dark";

  return (
    <header className="flex items-stretch gap-6 border-b border-rule bg-paper px-5 py-3">
      <div className="flex items-baseline gap-2.5">
        <h1 className="font-serif text-fs-26 font-medium italic leading-none tracking-tight text-ink">
          dirt<span className="text-accent-magenta">.</span>
        </h1>
        <span
          aria-hidden="true"
          className="mx-1.5 mb-1.5 inline-block h-px w-7 self-end bg-rule-strong"
        />
        {growContext ? (
          <p className="font-mono text-fs-10 uppercase tracking-cap-wide text-ink-3">
            Day {growContext.dayNumber} · {growContext.strain}
          </p>
        ) : null}
      </div>
      <nav aria-label="Primary" className="mx-auto flex items-center gap-1.5">
        {TABS.map(({ label, path }) => {
          const active = pathname === path;
          return (
            <button
              key={path}
              type="button"
              onClick={() => {
                void navigate({ to: path });
              }}
              aria-current={active ? "page" : undefined}
              className={
                active
                  ? "border border-ink bg-paper-2 px-4.5 py-2 font-sans text-fs-11 font-semibold uppercase tracking-cap-ui text-ink transition"
                  : "border border-rule px-4.5 py-2 font-sans text-fs-11 font-semibold uppercase tracking-cap-ui text-ink-3 transition hover:border-rule-strong hover:text-ink"
              }
            >
              {label}
            </button>
          );
        })}
      </nav>
      <div className="flex items-center gap-4.5 font-mono text-fs-11 text-ink-3">
        <button
          type="button"
          aria-label={`Switch to ${nextTheme} theme`}
          onClick={toggleTheme}
          className="border border-rule px-2.5 py-1.25 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition hover:border-ink-2 hover:text-ink"
        >
          <span aria-hidden="true" className="mr-1">
            ◐
          </span>
          Auto
        </button>
        <button
          type="button"
          onClick={() => {
            void navigate({ to: "/" });
          }}
          className="border border-rule px-2.5 py-1.25 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition hover:border-ink-2 hover:text-ink"
        >
          Log out
        </button>
      </div>
    </header>
  );
}
