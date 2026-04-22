// Dashboard humidifier tile.
//
// Renders the current humidifier on/off state plus two secondary figures
// sourced from /api/humidifier/state:
//   - duration since the last on/off transition (derived from duration_s),
//   - cycles in the last 24h (cycles_24h).
//
// Trusting the backend's duration_s over `new Date() - new Date(since)` is
// deliberate: the backend stamps both fields at its own request time, and
// re-deriving against the client clock introduces drift (and flakey tests
// when the mock's fixed `since` drifts past "now").
//
// Accessibility contract the e2e spec relies on:
//   - <article aria-label="Humidifier">           — one tile, queryable via
//                                                   getByRole("article",
//                                                     { name: "Humidifier" }).
//   - <h2>Humidifier</h2>                         — heading inside the tile.
//   - role="status" with aria-label="Humidifier   — the on/off word; text is
//     state">                                       "ON" or "OFF".
//   - data-labeled element for duration + cycles  — rendered as labeled
//                                                   pairs; the spec asserts
//                                                   by visible text +
//                                                   accessible name rather
//                                                   than data-testid.
//
// No data-testid, no sr-only duplicates. The markers above are idiomatic
// ARIA surfaces that double as screen-reader affordances.
import type { ReactNode } from "react";

type HumidifierTileProps = {
  /** ON = true, OFF = false. */
  on: boolean;
  /** Seconds since the last transition; formatted human-readable below. */
  durationS: number;
  /** Count of off→on transitions in the last 24h. */
  cycles24h: number;
};

// Format seconds into a compact "Hh Mm" / "Mm" / "Ss" string. The
// dashboard doesn't need precision beyond the minute for durations over a
// minute, so a coarse breakdown is fine and keeps the tile visually
// aligned with the gauges above it.
function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remMinutes = minutes % 60;
  return remMinutes === 0 ? `${hours}h` : `${hours}h ${remMinutes}m`;
}

// ON = magenta accent (matches the gauges' crit-style border emphasis for
// live events); OFF = muted rule. Keeps the tile's visual weight in line
// with the sensor gauge row so the dashboard reads evenly.
export function HumidifierTile({
  on,
  durationS,
  cycles24h,
}: HumidifierTileProps): ReactNode {
  const borderClass = on ? "border-accent-magenta" : "border-rule";
  const textClass = on ? "text-accent-magenta" : "text-ink-3";
  return (
    <article
      aria-label="Humidifier"
      className={`flex flex-col gap-3 border bg-paper p-5 ${borderClass}`}
    >
      <header className="flex items-baseline justify-between gap-2">
        <h2 className="font-mono text-xs uppercase tracking-caps text-ink-2">
          Humidifier
        </h2>
        <span
          role="status"
          aria-label="Humidifier state"
          className={`font-mono text-xs uppercase tracking-caps ${textClass}`}
          data-on={on}
        >
          {on ? "ON" : "OFF"}
        </span>
      </header>
      <div className="grid grid-cols-2 gap-2">
        <fieldset
          aria-label="Duration since last transition"
          className="flex flex-col gap-1 border-0 p-0"
        >
          <legend className="font-mono text-xs uppercase tracking-caps text-ink-3">
            Since
          </legend>
          <p className="font-serif text-2xl italic text-ink">
            {formatDuration(durationS)}
          </p>
        </fieldset>
        <fieldset
          aria-label="Cycles in last 24 hours"
          className="flex flex-col gap-1 border-0 p-0"
        >
          <legend className="font-mono text-xs uppercase tracking-caps text-ink-3">
            Cycles/24h
          </legend>
          <p className="font-serif text-2xl italic text-ink">{cycles24h}</p>
        </fieldset>
      </div>
    </article>
  );
}
