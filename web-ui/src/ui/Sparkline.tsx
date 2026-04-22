// Single history tile for the dashboard history grid.
//
// Fetches /api/sensors/history is delegated to the parent; this component
// is purely presentational and renders:
//   - a translucent area fill under the line + the polyline itself
//   - a shared crosshair: a dashed vertical line + data-point dot at the
//     `hoverIndex` supplied by the parent (null → no crosshair)
//   - an accessible tooltip (role="tooltip") showing value + unit when a
//     point is hovered, positioned horizontally over the hovered bucket
//
// Styling is ported from debug/webapp.zip/components/dashboard.{jsx,css}:
// a ◆ glyph + mixed-case label (not an uppercase eyebrow), no right-
// aligned unit chip. The unit still threads through to the tooltip.
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
import type { ReactNode } from "react";

interface HistoryPoint {
  ts: string;
  value: number;
}

type SparklineAccent = "temp" | "humidity" | "vpd" | "moisture" | "neutral";

interface SparklineProps {
  /** Metric display name; the article's accessible name + heading text. */
  name: string;
  /** Bucketed series for the current range. Empty while loading. */
  points: readonly HistoryPoint[];
  /** Unit string from the /api/sensors/history envelope (e.g. "°F", "kPa"). */
  unit: string;
  /** Sensor accent (line + marker + diamond + area-fill colour). */
  accent?: SparklineAccent;
  /**
   * Shared crosshair index across the history grid; null = no hover.
   * Derived from the parent's pointer-move handler.
   */
  hoverIndex: number | null;
  /** Called when the pointer moves over a bucket in this sparkline. */
  onHoverIndex: (index: number | null) => void;
}

const ACCENT_STROKE: Record<SparklineAccent, string> = {
  temp: "stroke-sensor-temp",
  humidity: "stroke-sensor-humidity",
  vpd: "stroke-sensor-vpd",
  moisture: "stroke-sensor-moisture",
  neutral: "stroke-ink",
};
const ACCENT_FILL: Record<SparklineAccent, string> = {
  temp: "fill-sensor-temp",
  humidity: "fill-sensor-humidity",
  vpd: "fill-sensor-vpd",
  moisture: "fill-sensor-moisture",
  neutral: "fill-ink",
};
const ACCENT_TEXT: Record<SparklineAccent, string> = {
  temp: "text-sensor-temp",
  humidity: "text-sensor-humidity",
  vpd: "text-sensor-vpd",
  moisture: "text-sensor-moisture",
  neutral: "text-ink",
};

const VIEWBOX_W = 100;
const VIEWBOX_H = 30;

function formatValue(value: number, unit: string): string {
  if (unit === "%") return `${Math.round(value)}${unit}`;
  return `${value.toFixed(1)}${unit}`;
}

export function Sparkline({
  name,
  points,
  unit,
  accent = "neutral",
  hoverIndex,
  onHoverIndex,
}: SparklineProps): ReactNode {
  const lineStroke = ACCENT_STROKE[accent];
  const areaFill = ACCENT_FILL[accent];
  const diamondColor = ACCENT_TEXT[accent];
  const tooltipColor = ACCENT_TEXT[accent];

  if (points.length === 0) {
    return (
      <article
        aria-label={`${name} sparkline`}
        className="flex flex-col gap-2 border-b border-r border-rule bg-paper-2 px-3.5 py-3"
      >
        <header className="flex items-center gap-2 font-sans text-fs-11 font-medium text-ink-2">
          <span aria-hidden="true" className={diamondColor}>
            ◆
          </span>
          <span>{name}</span>
        </header>
        <p className="font-mono text-fs-11 text-ink-3">—</p>
      </article>
    );
  }

  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = points.length === 1 ? 0 : VIEWBOX_W / (points.length - 1);
  const yFor = (v: number): number => VIEWBOX_H - ((v - min) / range) * VIEWBOX_H;
  const xFor = (i: number): number => (points.length === 1 ? VIEWBOX_W / 2 : i * stepX);

  const linePath = points
    .map((p, i) => {
      const cmd = i === 0 ? "M" : "L";
      return `${cmd} ${xFor(i).toFixed(2)} ${yFor(p.value).toFixed(2)}`;
    })
    .join(" ");
  const areaPath = `${linePath} L ${VIEWBOX_W.toFixed(2)} ${VIEWBOX_H} L 0 ${VIEWBOX_H} Z`;

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
  const hovered = clampedHover === null ? null : (points[clampedHover] ?? null);
  const hoverX = clampedHover === null ? null : xFor(clampedHover);
  const hoverY = hovered ? yFor(hovered.value) : null;
  const hoverRatio =
    clampedHover === null ? null : clampedHover / (points.length - 1 || 1);

  return (
    <article
      aria-label={`${name} sparkline`}
      className="flex flex-col gap-2 border-b border-r border-rule bg-paper-2 px-3.5 py-3"
    >
      <header className="flex items-center gap-2 font-sans text-fs-11 font-medium text-ink-2">
        <span aria-hidden="true" className={diamondColor}>
          ◆
        </span>
        <span>{name}</span>
      </header>
      <div className="relative cursor-crosshair">
        <svg
          aria-label="sparkline"
          role="img"
          viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
          preserveAspectRatio="none"
          className="block h-10 w-full"
          onPointerMove={handleMove}
          onPointerLeave={() => {
            onHoverIndex(null);
          }}
        >
          <title>{`${name} — ${points.length} points`}</title>
          <path d={areaPath} className={areaFill} opacity="0.1" />
          <path
            d={linePath}
            className={lineStroke}
            strokeWidth="0.8"
            fill="none"
            vectorEffect="non-scaling-stroke"
          />
          {hoverX !== null && hoverY !== null ? (
            <g aria-label="crosshair">
              <line
                x1={hoverX}
                y1={0}
                x2={hoverX}
                y2={VIEWBOX_H}
                className="stroke-ink"
                strokeWidth="0.4"
                strokeDasharray="1 1"
                vectorEffect="non-scaling-stroke"
                opacity="0.55"
              />
              <circle
                cx={hoverX}
                cy={hoverY}
                r="1.3"
                className={`${ACCENT_FILL[accent]} stroke-paper`}
                strokeWidth="0.5"
                vectorEffect="non-scaling-stroke"
              />
            </g>
          ) : null}
        </svg>
        {hovered !== null && hoverRatio !== null ? (
          <span
            role="tooltip"
            data-hover-index={clampedHover ?? undefined}
            // eslint-disable-next-line no-restricted-syntax -- runtime-computed hover position; not expressible in build-time Tailwind classes
            style={{ left: `${hoverRatio * 100}%` }}
            className={`pointer-events-none absolute -top-3.5 -translate-x-1/2 whitespace-nowrap border border-rule-strong bg-paper px-1.5 py-px font-mono text-fs-10 tabular-nums ${tooltipColor}`}
          >
            {formatValue(hovered.value, unit)}
          </span>
        ) : null}
      </div>
    </article>
  );
}
