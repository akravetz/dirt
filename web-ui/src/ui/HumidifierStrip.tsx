// Dashboard humidifier duty-cycle tile.
//
// Renders as the sixth cell in the History grid (same visual shell as a
// sparkline tile). One SVG rect per transition from /api/humidifier/
// history: width proportional to the equal-segment division of the
// viewport, fill keyed by the transition's `on` bit (magenta when on,
// transparent when off).
//
// Hovering an on-cycle rect surfaces a tooltip with the cycle's local
// start and end times. The end of an on-cycle is the next transition's
// ts (which is necessarily `on=false` — the off transition that closed
// the cycle). If the on-cycle is the most recent point in the series
// (no subsequent off transition yet), the tooltip reads "ongoing".
//
// Accessibility contract the e2e spec relies on:
//   - <article aria-label="Humidifier duty cycle">  — the tile container.
//   - <svg aria-label="humidifier strip">           — the chart surface.
//   - <rect aria-label="humidifier segment"         — one per transition;
//     data-on={"true"|"false"}>                       getByLabel("humidifier
//                                                     segment") count
//                                                     == points.length.
import { type ReactNode, useState } from "react";

interface HumidifierTransition {
  ts: string;
  on: boolean;
}

interface HumidifierStripProps {
  /** Ordered transitions for the active range (earliest → latest). */
  points: readonly HumidifierTransition[];
}

const VIEWBOX_W = 100;
const VIEWBOX_H = 30;
// On-segments occupy the vertical middle half of the tile (y = 10.5 to
// 25.5) to match the mock's `y={h*0.35}` / `height={h*0.5}` rects.
const BAR_Y = VIEWBOX_H * 0.35;
const BAR_H = VIEWBOX_H * 0.5;

// "Apr 22 14:03" — compact local time that fits in the tooltip for
// either 24h or 7d ranges. The date + time combo survives ranges that
// span midnight without us branching by range prop.
const TIME_FMT = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function formatLocal(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return TIME_FMT.format(d);
}

export function HumidifierStrip({ points }: HumidifierStripProps): ReactNode {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  if (points.length === 0) {
    return (
      <article
        aria-label="Humidifier duty cycle"
        className="flex flex-col gap-2 border-b border-r border-rule bg-paper-2 px-3.5 py-3"
      >
        <header className="flex items-center gap-2 font-sans text-fs-11 font-medium text-ink-2">
          <span aria-hidden="true" className="text-accent-magenta">
            ◆
          </span>
          <span>Humidifier · duty cycle</span>
        </header>
        <p className="font-mono text-fs-11 text-ink-3">No transitions in range.</p>
      </article>
    );
  }

  const n = points.length;
  const segWidth = VIEWBOX_W / n;
  // Mock uses a small gap between bars (`width: w/n * 0.95`). Preserving
  // that here keeps the ON bars visually distinct at high point counts.
  const barWidth = segWidth * 0.95;

  const hovered = hoverIdx !== null ? points[hoverIdx] : null;
  const hoveredIsOn = hovered?.on === true;
  const hoverStart = hoveredIsOn ? formatLocal(hovered.ts) : null;
  // End of the cycle is the next transition (the off transition that
  // closed it). Undefined when the on-cycle is the last point in the
  // series — i.e. still running, which we surface as "ongoing".
  const hoverEndTs =
    hoverIdx !== null && hoverIdx + 1 < n ? points[hoverIdx + 1]?.ts : undefined;
  const hoverEnd = hoverEndTs === undefined ? "ongoing" : formatLocal(hoverEndTs);
  const hoverCenterPct =
    hoverIdx !== null ? ((hoverIdx + 0.5) * segWidth) / VIEWBOX_W : null;

  return (
    <article
      aria-label="Humidifier duty cycle"
      className="flex flex-col gap-2 border-b border-r border-rule bg-paper-2 px-3.5 py-3"
    >
      <header className="flex items-center gap-2 font-sans text-fs-11 font-medium text-ink-2">
        <span aria-hidden="true" className="text-accent-magenta">
          ◆
        </span>
        <span>Humidifier · duty cycle</span>
      </header>
      <div className="relative">
        <svg
          aria-label="humidifier strip"
          role="img"
          viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
          preserveAspectRatio="none"
          className="block h-10 w-full"
          onPointerLeave={() => {
            setHoverIdx(null);
          }}
        >
          <title>Humidifier on/off transitions</title>
          {points.map((point, i) => (
            <rect
              key={point.ts}
              aria-label="humidifier segment"
              data-on={point.on}
              x={i * segWidth}
              y={BAR_Y}
              width={barWidth}
              height={BAR_H}
              className={
                point.on ? "cursor-pointer fill-accent-magenta" : "fill-transparent"
              }
              opacity={point.on ? 0.7 : 0}
              onPointerEnter={() => {
                if (point.on) setHoverIdx(i);
              }}
            />
          ))}
        </svg>
        {hoveredIsOn && hoverStart !== null && hoverCenterPct !== null ? (
          <div
            role="tooltip"
            // eslint-disable-next-line no-restricted-syntax -- runtime-computed hover position; not expressible in build-time Tailwind classes
            style={{ left: `${hoverCenterPct * 100}%` }}
            className="pointer-events-none absolute -top-3.5 -translate-x-1/2 whitespace-nowrap border border-rule-strong bg-paper px-2 py-0.5 font-mono text-fs-10 tabular-nums text-accent-magenta"
          >
            {hoverStart} → {hoverEnd}
          </div>
        ) : null}
      </div>
    </article>
  );
}
