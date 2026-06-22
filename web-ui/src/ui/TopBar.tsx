import { Link, linkOptions } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { storage } from "@/shared/storage";

const TABS = linkOptions([
  { label: "Tents", to: "/tents" },
  { label: "Plants", to: "/plants" },
  { label: "Seeds", to: "/seeds" },
]);

const THEME_STORAGE_KEY = "dirt.theme";
type Theme = "light" | "dark";
type GrowStage = "veg" | "flower_early" | "flower_late";

type GrowContext = {
  dayNumber: number;
  flowerWeekNumber: number | null;
  lights: {
    offLocal: string;
    onLocal: string;
  };
  stage: GrowStage;
  strain: string;
};

function readStoredTheme(): Theme {
  const raw = storage.get(THEME_STORAGE_KEY);
  return raw === "dark" ? "dark" : "light";
}

interface TopBarProps {
  /**
   * Grow-context summary sourced from GET /api/grow/current by the root route
   * (ui/ can't import api-client under TS-02). Omit while the query is loading
   * or on pre-auth screens that predate the grow identity (the TopBar itself is
   * already hidden on /login).
   */
  growContext?: GrowContext | null;
  onLogout: () => void;
}

function stageLabel(stage: GrowStage): string {
  if (stage === "veg") return "Veg";
  return stage === "flower_early" ? "Flower early" : "Flower late";
}

function shortLocalTime(value: string): string {
  return value.slice(0, 5);
}

export function TopBar({ growContext = null, onLogout }: TopBarProps) {
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
    <header className="flex flex-wrap items-center gap-x-5 gap-y-3 border-b border-rule bg-paper px-5 py-3">
      <div className="flex min-w-0 items-baseline gap-2.5">
        <h1 className="font-serif text-fs-26 font-medium italic leading-none tracking-tight text-ink">
          dirt<span className="text-accent-magenta">.</span>
        </h1>
        <span
          aria-hidden="true"
          className="mx-1.5 mb-1.5 inline-block h-px w-7 self-end bg-rule-strong"
        />
        {growContext ? (
          <p className="font-mono text-fs-10 uppercase tracking-cap-wide text-ink-3">
            Day {growContext.dayNumber} · {stageLabel(growContext.stage)}
            {growContext.flowerWeekNumber === null
              ? null
              : ` · W${growContext.flowerWeekNumber}`}{" "}
            · {shortLocalTime(growContext.lights.onLocal)}-
            {shortLocalTime(growContext.lights.offLocal)} · {growContext.strain}
          </p>
        ) : null}
      </div>
      <nav
        aria-label="Primary"
        className="order-3 flex w-full items-center gap-1.5 overflow-x-auto sm:order-none sm:mx-auto sm:w-auto"
      >
        {TABS.map((tab) => (
          <Link
            key={tab.to}
            {...tab}
            activeProps={{ "aria-current": "page" }}
            className="shrink-0 border border-rule px-4.5 py-2 font-sans text-fs-11 font-semibold uppercase tracking-cap-ui text-ink-3 transition hover:border-rule-strong hover:text-ink data-[status=active]:border-ink data-[status=active]:bg-paper-2 data-[status=active]:text-ink"
          >
            {tab.label}
          </Link>
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-2 font-mono text-fs-11 text-ink-3 sm:gap-4.5">
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
          onClick={onLogout}
          className="border border-rule px-2.5 py-1.25 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition hover:border-ink-2 hover:text-ink"
        >
          Log out
        </button>
      </div>
    </header>
  );
}
