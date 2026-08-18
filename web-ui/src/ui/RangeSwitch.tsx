// 1h / 24h / 7d / 30d / 90d range switcher.
//
// Renders toggle buttons wrapped in a role="group" — these are
// mutually exclusive window selectors, but modelling them as HTML
// <input type="radio"> fights the visual design (button-shaped chips
// with a colored border on the active one). Instead, each <button>
// carries aria-pressed reflecting the active selection, which is the
// standard ARIA toggle-button idiom. The group's accessible name lets
// the e2e scope its locator without inventing a data-testid.
//
// The UI owns the fixed order and labels. Feature callers pass this union
// directly to generated API query parameters, so removed or renamed backend
// values fail typecheck without making this presentational layer import the
// API client.
import type { ReactNode } from "react";

export type SparklineRange = "1h" | "24h" | "7d" | "30d" | "90d";

const RANGES: readonly SparklineRange[] = ["1h", "24h", "7d", "30d", "90d"] as const;

interface RangeSwitchProps {
  value: SparklineRange;
  onChange: (next: SparklineRange) => void;
}

export function RangeSwitch({ value, onChange }: RangeSwitchProps): ReactNode {
  return (
    <fieldset
      aria-label="Sparkline range"
      className="inline-flex flex-wrap items-center gap-1 border-0 p-0 font-mono text-xs uppercase tracking-caps"
    >
      {RANGES.map((range) => {
        const active = range === value;
        return (
          <button
            key={range}
            type="button"
            aria-pressed={active}
            onClick={() => {
              onChange(range);
            }}
            className={
              active
                ? "border border-accent-magenta bg-paper px-2 py-1 text-ink sm:px-3"
                : "border border-rule bg-paper px-2 py-1 text-ink-3 hover:text-ink sm:px-3"
            }
          >
            {range}
          </button>
        );
      })}
    </fieldset>
  );
}
