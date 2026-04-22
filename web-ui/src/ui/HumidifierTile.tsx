// Dashboard humidifier tile.
//
// Renders the current humidifier on/off state plus two secondary figures
// sourced from /api/humidifier/state:
//   - duration since the last on/off transition (derived from duration_s),
//   - cycles in the last 24h (cycles_24h).
//
// Layout — ported from debug/webapp/components/dashboard.{jsx,css}:
//   row 1: pulse dot + ON/OFF word (magenta when on, muted when off)
//          with the elapsed duration right-aligned on the same row;
//   row 2: a decorative mini duty-cycle strip echoing the History grid's
//          humidifier-duty-cycle tile (alternating magenta bars);
//   row 3: "HUMIDIFIER" eyebrow;
//   row 4: "{cycles_24h} cycles / 24h" in magenta accent.
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
//   - group[aria-label="Duration since last       — wraps the elapsed token.
//     transition"]
//   - group[aria-label="Cycles in last 24 hours"] — wraps the "N cycles" line.
import type { ReactNode } from "react";

type HumidifierTileProps = {
  /** ON = true, OFF = false. */
  on: boolean;
  /** Seconds since the last transition; formatted human-readable below. */
  durationS: number;
  /** Count of off→on transitions in the last 24h. */
  cycles24h: number;
};

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    const remSeconds = seconds % 60;
    return remSeconds === 0 ? `${minutes}m` : `${minutes}m ${remSeconds}s`;
  }
  const hours = Math.floor(minutes / 60);
  const remMinutes = minutes % 60;
  return remMinutes === 0 ? `${hours}h` : `${hours}h ${remMinutes}m`;
}

// Decorative mini duty-cycle viz — matches the mock's fake-bar pattern so
// the tile reads as a compressed echo of the History grid's humidifier
// strip. Not data-driven: /api/humidifier/state doesn't ship a transition
// series, and plumbing /api/humidifier/history here would duplicate the
// History strip. The pattern is purely visual signal.
const MINI_BARS = Array.from({ length: 32 }, (_, i) => ({
  x: i * 3.1,
  on: Math.floor(i / 2.8) % 2 === 0,
}));

export function HumidifierTile({
  on,
  durationS,
  cycles24h,
}: HumidifierTileProps): ReactNode {
  const stateTextClass = on ? "text-accent-magenta" : "text-ink-3";
  return (
    <article
      aria-label="Humidifier"
      className="flex flex-col gap-1.5 border-l border-rule-strong bg-paper-3 p-4"
    >
      <header className="flex items-center gap-2 border-b border-rule pb-1">
        {on ? <span aria-hidden="true" className="humidifier-dot" /> : null}
        <span
          role="status"
          aria-label="Humidifier state"
          className={`font-mono text-fs-13 font-semibold uppercase tracking-cap-field ${stateTextClass}`}
          data-on={on}
        >
          {on ? "ON" : "OFF"}
        </span>
        {/* biome-ignore lint/a11y/useSemanticElements: role=group is a lightweight SR-only grouping; <fieldset> is for form controls, not a label/value pair */}
        <span
          role="group"
          aria-label="Duration since last transition"
          className="ml-auto font-mono text-fs-11 text-ink-3"
        >
          {formatDuration(durationS)}
        </span>
      </header>
      <svg
        aria-hidden="true"
        viewBox="0 0 100 18"
        preserveAspectRatio="none"
        className="block h-7 w-full"
      >
        {MINI_BARS.map(({ x, on: barOn }) =>
          barOn ? (
            <rect
              key={x}
              x={x}
              y="4"
              width="2.4"
              height="10"
              className="fill-accent-magenta"
              opacity="0.75"
            />
          ) : null,
        )}
      </svg>
      <h2 className="font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
        Humidifier
      </h2>
      {/* biome-ignore lint/a11y/useSemanticElements: role=group is a lightweight SR-only grouping; <fieldset> is for form controls, not a label/value pair */}
      <p
        role="group"
        aria-label="Cycles in last 24 hours"
        className="flex items-baseline gap-1"
      >
        <span className="font-mono text-fs-14 font-semibold tabular-nums text-accent-magenta">
          {cycles24h} cycles
        </span>
        <span className="font-mono text-fs-11 text-ink-3">/ 24h</span>
      </p>
    </article>
  );
}
