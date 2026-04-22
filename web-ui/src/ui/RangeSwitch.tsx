// 1h / 24h / 7d range switcher.
//
// Renders three toggle buttons wrapped in a role="group" — these are
// mutually exclusive window selectors, but modelling them as HTML
// <input type="radio"> fights the visual design (button-shaped chips
// with a colored border on the active one). Instead, each <button>
// carries aria-pressed reflecting the active selection, which is the
// standard ARIA toggle-button idiom. The group's accessible name lets
// the e2e scope its locator without inventing a data-testid.
//
// The set of valid ranges is pinned to the SensorsHistoryResponse.range
// enum in the OpenAPI contract (components.schemas.Range). ui/ can't
// import from api-client/ under the boundaries rule, so the enum lives
// here as a local literal union; any drift from the contract fails
// typecheck at the consumer (routes/index.tsx) where `Range` is passed
// through from the api-client types.
import type { ReactNode } from "react";

export type SparklineRange = "1h" | "24h" | "7d";

const RANGES: readonly SparklineRange[] = ["1h", "24h", "7d"] as const;

interface RangeSwitchProps {
  value: SparklineRange;
  onChange: (next: SparklineRange) => void;
}

export function RangeSwitch({ value, onChange }: RangeSwitchProps): ReactNode {
  return (
    <fieldset
      aria-label="Sparkline range"
      className="inline-flex items-center gap-1 border-0 p-0 font-mono text-xs uppercase tracking-caps"
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
                ? "border border-accent-magenta bg-paper px-3 py-1 text-ink"
                : "border border-rule bg-paper px-3 py-1 text-ink-3 hover:text-ink"
            }
          >
            {range}
          </button>
        );
      })}
    </fieldset>
  );
}
