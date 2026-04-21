import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { storage } from "@/shared/storage";

// Primary nav tabs. Paths match the file-based routes under src/routes/;
// TanStack Router's generated tree gives `navigate({ to })` type safety
// across this literal union.
const TABS = [
  { label: "Dashboard", path: "/" },
  { label: "Live", path: "/live" },
  { label: "Wiki", path: "/wiki" },
] as const;

type TabPath = (typeof TABS)[number]["path"];

const THEME_STORAGE_KEY = "dirt.theme";
const THEMES = ["light", "dark"] as const;
type Theme = (typeof THEMES)[number];

function readStoredTheme(): Theme {
  const raw = storage.get(THEME_STORAGE_KEY);
  return raw === "dark" ? "dark" : "light";
}

export function TopBar() {
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
    <header className="flex items-center justify-between gap-6 border-b border-rule bg-paper px-6 py-4">
      <h1 className="font-serif text-3xl italic text-ink">
        dirt<span className="text-accent-magenta">.</span>
      </h1>
      <nav
        aria-label="Primary"
        className="flex items-center gap-1 font-mono text-xs uppercase tracking-caps"
      >
        {TABS.map(({ label, path }) => {
          const active = pathname === path;
          return (
            <button
              key={path}
              type="button"
              onClick={() => {
                void navigate({ to: path satisfies TabPath });
              }}
              aria-current={active ? "page" : undefined}
              className={
                active
                  ? "border-b-2 border-accent-magenta px-3 py-2 text-ink"
                  : "border-b-2 border-transparent px-3 py-2 text-ink-3 hover:text-ink"
              }
            >
              {label}
            </button>
          );
        })}
      </nav>
      <div className="flex items-center gap-2 font-mono text-xs uppercase tracking-caps">
        <button
          type="button"
          aria-label={`Switch to ${nextTheme} theme`}
          onClick={toggleTheme}
          className="border border-rule px-3 py-2 text-ink-3 hover:text-ink"
        >
          {theme === "dark" ? "Light" : "Dark"}
        </button>
        <button
          type="button"
          onClick={() => {
            void navigate({ to: "/" });
          }}
          className="border border-rule px-3 py-2 text-ink-3 hover:text-ink"
        >
          Log out
        </button>
      </div>
    </header>
  );
}
