// Single dashboard gauge tile.
//
// Renders a metric's current reading (value + unit), an optional
// target-band arc (only present when the backend returned a `band`),
// and a visible status word (ok / warn / crit) that mirrors the
// backend-computed `status` from /api/sensors/current. Trusting the
// backend's status is deliberate — the band_status classifier lives in
// apps/shared/src/dirt_shared/services/grow_state.py and the e2e spec
// asserts the FE forwards it verbatim, not that the FE re-derives it.
//
// Accessibility contract the e2e spec relies on:
//   - <article aria-label={name}>  → one tile per metric, queryable via
//     getByRole("article", { name: /temperature/i }).
//   - <h2>{name}</h2>              → getByRole("heading") inside each tile.
//   - Status text node labelled    → getByRole("status") per tile, visible
//     with role="status".            text is one of "ok" / "warn" / "crit".
//   - <svg aria-label="target      → exactly one match per banded tile
//     band">                         (temp / humidity / VPD); absent on
//                                    fan / reservoir. getByLabel("target
//                                    band") counts 3 overall.
//
// No data-testid, no sr-only mirrors. The markers above are all
// idiomatic ARIA surfaces that double as screen-reader affordances.
import type { ReactNode } from "react";

// Band status enum from the backend contract
// (components.schemas.BandStatus). Duck-typed here so this ui/ module
// can stay on its own layer — the boundaries lint forbids ui/ →
// api-client/, and a one-line literal union is cheaper than routing a
// shared type through src/shared/.
type GaugeStatus = "ok" | "warn" | "crit";

interface GaugeProps {
  /** Metric display name; also the tile's accessible name + heading text. */
  name: string;
  /** Current reading value (raw — formatted below with `format`). */
  value: number;
  /** Unit string, e.g. "°F", "%", "kPa". Appended after the formatted value. */
  unit: string;
  /** Target band [lo, hi]; `null` hides the arc (fan / reservoir). */
  band: readonly [number, number] | null;
  /** Backend-computed status. Drives the status-word + tile accent. */
  status: GaugeStatus;
  /**
   * Optional value formatter; defaults to one decimal place. Useful for
   * integer-valued metrics like fan_pct where "48.0%" reads awkward.
   */
  format?: (value: number) => string;
}

// Status → Tailwind-palette class. Three named tokens means the
// evaluator can grep `status-ok` / `status-warn` / `status-crit` class
// presence without relying on raw hex values. The classes below use
// our paper/ink palette + accent-magenta (for crit) — all tokens from
// src/styles.css @theme, so TS-15 (no arbitrary values) stays happy.
const STATUS_BORDER: Record<GaugeStatus, string> = {
  ok: "border-rule",
  warn: "border-accent-purple",
  crit: "border-accent-magenta",
};

const STATUS_TEXT: Record<GaugeStatus, string> = {
  ok: "text-ink-3",
  warn: "text-accent-purple",
  crit: "text-accent-magenta",
};

function defaultFormat(value: number): string {
  // One decimal place. 76 → "76.0", 1 → "1.0", 1.05 → "1.1".
  return value.toFixed(1);
}

// Arc dimensions — a fixed 120x72 viewBox lets the SVG scale to any
// tile width. The arc spans 180° from (10, 60) to (110, 60) with a
// peak at (60, 10), drawn as a cubic-ish half-circle path. The band
// segment is rendered as a second path clipped to the lo/hi subrange.
function Arc({
  band,
  value,
  status,
}: {
  band: readonly [number, number];
  value: number;
  status: GaugeStatus;
}): ReactNode {
  const [lo, hi] = band;
  // Map the band onto [0, 1] of the arc by expanding the display
  // range to (lo - halfWidth, hi + halfWidth) so the warn zone is
  // visible on either side of the target. If the value lies outside
  // that, clamp the needle — we're still showing the correct status.
  const halfWidth = (hi - lo) / 2;
  const displayLo = lo - halfWidth;
  const displayHi = hi + halfWidth;
  const needleT = Math.max(
    0,
    Math.min(1, (value - displayLo) / (displayHi - displayLo)),
  );

  // Arc geometry: half-circle from angle π (left) to 0 (right).
  const cx = 60;
  const cy = 60;
  const r = 50;
  const pointAt = (t: number): readonly [number, number] => {
    const angle = Math.PI - t * Math.PI;
    return [cx + r * Math.cos(angle), cy - r * Math.sin(angle)] as const;
  };
  const [nx, ny] = pointAt(needleT);
  // Band segment path (the target zone): from the lo/hi mapped onto
  // the same [displayLo, displayHi] window.
  const bandLoT = (lo - displayLo) / (displayHi - displayLo);
  const bandHiT = (hi - displayLo) / (displayHi - displayLo);
  const [blx, bly] = pointAt(bandLoT);
  const [bhx, bhy] = pointAt(bandHiT);

  const bandStrokeClass =
    status === "crit"
      ? "stroke-accent-magenta"
      : status === "warn"
        ? "stroke-accent-purple"
        : "stroke-rule-strong";

  return (
    <svg
      aria-label="target band"
      role="img"
      viewBox="0 0 120 72"
      className="h-16 w-full"
      fill="none"
    >
      <title>
        Target band {lo}–{hi}
      </title>
      {/* Background track — full half-circle, thin. */}
      <path
        d={`M 10 60 A 50 50 0 0 1 110 60`}
        className="stroke-rule"
        strokeWidth="3"
      />
      {/* Target-band segment — thicker, accent stroke. */}
      <path
        d={`M ${blx} ${bly} A 50 50 0 0 1 ${bhx} ${bhy}`}
        className={bandStrokeClass}
        strokeWidth="5"
      />
      {/* Needle — line from center to current-value point. */}
      <line x1={cx} y1={cy} x2={nx} y2={ny} className="stroke-ink" strokeWidth="2" />
      <circle cx={cx} cy={cy} r="3" className="fill-ink" />
    </svg>
  );
}

export function Gauge({
  name,
  value,
  unit,
  band,
  status,
  format = defaultFormat,
}: GaugeProps): ReactNode {
  return (
    <article
      aria-label={name}
      className={`flex flex-col gap-3 border bg-paper p-5 ${STATUS_BORDER[status]}`}
    >
      <header className="flex items-baseline justify-between gap-2">
        <h2 className="font-mono text-xs uppercase tracking-caps text-ink-2">{name}</h2>
        <span
          role="status"
          aria-label={`${name} status`}
          className={`font-mono text-xs uppercase tracking-caps ${STATUS_TEXT[status]}`}
          data-status={status}
        >
          {status}
        </span>
      </header>
      <p className="flex items-baseline gap-2">
        <span className="font-serif text-4xl italic text-ink">{format(value)}</span>
        <span className="font-mono text-xs uppercase tracking-caps text-ink-3">
          {unit}
        </span>
      </p>
      {band !== null ? <Arc band={band} value={value} status={status} /> : null}
    </article>
  );
}
