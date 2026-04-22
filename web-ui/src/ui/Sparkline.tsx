// Single sparkline tile for the dashboard sparklines strip.
//
// Fetches /api/sensors/history is delegated to the parent; this component
// is purely presentational and renders:
//   - an SVG polyline over the (ts, value) points
//   - a shared crosshair: a vertical line + data-point dot at the
//     `hoverIndex` supplied by the parent (null → no crosshair)
//   - an accessible tooltip (role="tooltip") showing value + unit when a
//     point is hovered
//
// Accessibility contract the e2e spec relies on:
//   - <article aria-label={`${name} sparkline`}>  — one per metric, so
//     getByRole("article", { name: /temperature sparkline/i }) resolves.
//   - <svg aria-label="sparkline" role="img">     — the chart surface
//     the test pointer-hovers on.
//   - <svg aria-label="crosshair">                — rendered only when
//     hoverIndex !== null. getByLabel("crosshair") count = 5 during hover.
//   - role="tooltip" element                       — visible when
//     hoverIndex !== null; textContent includes the formatted value and
//     the unit string so the e2e can assert per-metric unit suffixes.
//
// Hover is kept at the index level (not pixel x): with shared series
// length per range, five sparklines crosshair at the same bucket index
// regardless of render width, so the crosshair is visually aligned on
// every tile.
import type { ReactNode } from "react";

interface HistoryPoint {
  ts: string;
  value: number;
}

interface SparklineProps {
  /** Metric display name; the article's accessible name + heading text. */
  name: string;
  /** Bucketed series for the current range. Empty while loading. */
  points: readonly HistoryPoint[];
  /** Unit string from the /api/sensors/history envelope (e.g. "°F", "kPa"). */
  unit: string;
  /**
   * Shared crosshair index across the sparkline strip; null = no hover.
   * Derived from the parent's pointer-move handler.
   */
  hoverIndex: number | null;
  /** Called when the pointer moves over a bucket in this sparkline. */
  onHoverIndex: (index: number | null) => void;
}

const VIEWBOX_W = 120;
const VIEWBOX_H = 32;
const PAD_Y = 3;

function formatValue(value: number, unit: string): string {
  // Integer-ish metrics read better without a decimal. The % units
  // (humidity_pct, fan_pct) are always integer-scale; everything else
  // gets one decimal.
  if (unit === "%") return `${Math.round(value)}${unit}`;
  return `${value.toFixed(1)}${unit}`;
}

export function Sparkline({
  name,
  points,
  unit,
  hoverIndex,
  onHoverIndex,
}: SparklineProps): ReactNode {
  if (points.length === 0) {
    return (
      <article
        aria-label={`${name} sparkline`}
        className="flex flex-col gap-2 border border-rule bg-paper p-3"
      >
        <header>
          <h3 className="font-mono text-xs uppercase tracking-caps text-ink-2">
            {name}
          </h3>
        </header>
        <p className="font-mono text-xs text-ink-3">—</p>
      </article>
    );
  }

  // Map (value, index) → SVG coordinates. Guard against a flat series
  // so the line renders at the midline instead of diverging.
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = points.length === 1 ? 0 : VIEWBOX_W / (points.length - 1);
  const yFor = (v: number): number =>
    VIEWBOX_H - PAD_Y - ((v - min) / range) * (VIEWBOX_H - 2 * PAD_Y);
  const xFor = (i: number): number => (points.length === 1 ? VIEWBOX_W / 2 : i * stepX);

  const pathD = points
    .map((p, i) => {
      const cmd = i === 0 ? "M" : "L";
      return `${cmd} ${xFor(i).toFixed(2)} ${yFor(p.value).toFixed(2)}`;
    })
    .join(" ");

  // Translate a pointer-move event inside the SVG to the nearest bucket
  // index. currentTarget's bounding rect is the reference so scaling
  // stays consistent when the SVG responds to tile width.
  const handleMove = (event: React.PointerEvent<SVGSVGElement>): void => {
    const rect = event.currentTarget.getBoundingClientRect();
    const relX = event.clientX - rect.left;
    if (rect.width <= 0) {
      onHoverIndex(null);
      return;
    }
    const ratio = Math.max(0, Math.min(1, relX / rect.width));
    const index = Math.round(ratio * (points.length - 1));
    onHoverIndex(index);
  };

  const clampedHover =
    hoverIndex === null ? null : Math.max(0, Math.min(points.length - 1, hoverIndex));
  const hovered = clampedHover === null ? null : points[clampedHover];
  const hoverX = clampedHover === null ? null : xFor(clampedHover);
  const hoverY = hovered ? yFor(hovered.value) : null;

  return (
    <article
      aria-label={`${name} sparkline`}
      className="flex flex-col gap-2 border border-rule bg-paper p-3"
    >
      <header className="flex items-baseline justify-between gap-2">
        <h3 className="font-mono text-xs uppercase tracking-caps text-ink-2">{name}</h3>
        {hovered ? (
          <span
            role="tooltip"
            className="font-mono text-xs text-ink"
            data-hover-index={clampedHover ?? undefined}
          >
            {formatValue(hovered.value, unit)}
          </span>
        ) : (
          <span className="font-mono text-xs text-ink-3" aria-hidden="true">
            {unit}
          </span>
        )}
      </header>
      <svg
        aria-label="sparkline"
        role="img"
        viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
        preserveAspectRatio="none"
        className="h-10 w-full"
        onPointerMove={handleMove}
        onPointerLeave={() => {
          onHoverIndex(null);
        }}
      >
        <title>{`${name} — ${points.length} points`}</title>
        <path d={pathD} className="stroke-ink" strokeWidth="1" fill="none" />
        {hoverX !== null && hoverY !== null ? (
          <g aria-label="crosshair">
            <line
              x1={hoverX}
              y1={0}
              x2={hoverX}
              y2={VIEWBOX_H}
              className="stroke-accent-magenta"
              strokeWidth="0.75"
            />
            <circle cx={hoverX} cy={hoverY} r="1.75" className="fill-accent-magenta" />
          </g>
        ) : null}
      </svg>
    </article>
  );
}
