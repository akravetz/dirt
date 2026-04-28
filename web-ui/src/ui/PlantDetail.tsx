// Plant-detail drawer — slides in over the dashboard when a plant is
// selected.
//
// Layout mirrors debug/webapp.zip/components/plant_detail.jsx:
//   - magenta/scrim overlay that fades in and closes the drawer on click;
//   - 720px drawer with left ink border and a slide-in animation;
//   - status tag (primary/secondary/retired) with colour-keyed border;
//   - moisture hero with numeric value + a horizontal target-band track;
//   - timeline with highlight rows that pick up a magenta accent;
//   - note block with an accent-purple left border;
//   - footer with the wiki path + close button.
//
// ARIA contract the e2e spec relies on:
//   - aside[role=dialog][aria-label="Plant detail"] — spec scope.
//   - heading level=2 with the plant name.
//   - role="status" + aria-label="Plant status" with title-cased text.
//   - region[name="Moisture"], region[name="Timeline"].
//   - Each timeline entry: aria-label="timeline entry" on a <li>, so
//     getByRole("listitem") and getByLabel("timeline entry") both
//     return the same count.
//   - ESC scoped onKeyDown → onClose.
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import { HoverTimestamp } from "@/ui/HoverTimestamp";
import {
  type PlantCode,
  STICKER_BG,
  STICKER_FILL,
  STICKER_STROKE,
  type StickerColor,
} from "@/ui/plant-types";
import { RangeSwitch, type SparklineRange } from "@/ui/RangeSwitch";

// react-markdown wraps output in <p> by default. Timeline entries sit
// inside <span>s and the note already has an italic <p> wrapper, so we
// strip the paragraph wrapper to keep the markdown inline.
const INLINE_MARKDOWN_COMPONENTS = {
  p: ({ children }: { children?: ReactNode }) => <>{children}</>,
};

interface TimelineEntry {
  date: string;
  day: number;
  text: string;
  highlight: boolean;
}
interface PlantNote {
  text: string;
  updated: string;
}
interface MoistureCurrent {
  current_pct: number | null;
  target: readonly [number, number] | number[] | null;
}
interface MoistureHistoryPoint {
  ts: string;
  value: number;
}

interface PlantDetailPayload {
  code: PlantCode;
  name: string;
  sticker_color: StickerColor;
  status: "primary" | "secondary" | "retired";
  label: string;
  moisture: MoistureCurrent;
  timeline: readonly TimelineEntry[];
  note: PlantNote | null;
  wiki_path: string;
}

interface PlantDetailProps {
  payload: PlantDetailPayload;
  moistureHistory: readonly MoistureHistoryPoint[];
  moistureRange: SparklineRange;
  onMoistureRangeChange: (next: SparklineRange) => void;
  onClose: () => void;
}

const RANGE_LABEL: Record<SparklineRange, string> = {
  "1h": "last 1h",
  "24h": "last 24h",
  "7d": "last 7d",
};

const STATUS_LABEL: Record<PlantDetailPayload["status"], string> = {
  primary: "Primary",
  secondary: "Secondary",
  retired: "Retired",
};

const STATUS_TAG_TONE: Record<PlantDetailPayload["status"], string> = {
  primary: "border-accent-magenta text-accent-magenta",
  secondary: "border-ink-3 text-ink-3",
  retired: "border-rule-strong text-ink-3",
};

const STATUS_TAG_LABEL: Record<PlantDetailPayload["status"], string> = {
  primary: "● primary keeper",
  secondary: "○ secondary",
  retired: "⌀ retired",
};

// Moisture hero band — absolute track spans 30%→85% soil moisture, with
// the target band highlighted. Positions use CSS calc against the
// hero-track width via grid percentages; pure SVG keeps TS-16 happy (no
// inline style attributes on HTML elements).
const TRACK_MIN = 30;
const TRACK_MAX = 85;
const TRACK_TICKS = [30, 45, 55, 70, 85] as const;

function MoistureHero({
  currentPct,
  target,
}: {
  currentPct: number | null;
  target: readonly [number, number] | null;
}): ReactNode {
  const hasTarget = target !== null;
  const lo = target?.[0] ?? null;
  const hi = target?.[1] ?? null;
  const pct = currentPct ?? TRACK_MIN;
  const pctFraction = (x: number): number =>
    ((x - TRACK_MIN) / (TRACK_MAX - TRACK_MIN)) * 100;
  const bandX = hasTarget ? pctFraction(lo as number) : 0;
  const bandW = hasTarget ? pctFraction(hi as number) - bandX : 0;
  const markerX = pctFraction(Math.max(TRACK_MIN, Math.min(TRACK_MAX, pct)));
  const statusText =
    currentPct === null
      ? "No reading"
      : !hasTarget
        ? "target unavailable"
        : currentPct < (lo as number)
          ? "below target — irrigation due"
          : currentPct > (hi as number)
            ? "above target — drying down"
            : "in target band";
  const dotClass =
    currentPct !== null &&
    hasTarget &&
    currentPct >= (lo as number) &&
    currentPct <= (hi as number)
      ? "text-sensor-vpd"
      : "text-accent-magenta";

  return (
    <section
      aria-label="Moisture"
      className="grid grid-cols-1 gap-8 border border-rule-strong bg-paper-2 p-6 md:grid-cols-[minmax(180px,240px)_1fr]"
    >
      <div className="flex flex-col gap-2">
        <h3 className="font-mono text-fs-10 uppercase tracking-cap-med text-ink-3">
          Soil Moisture · now
        </h3>
        <p className="flex items-baseline gap-1">
          <span className="font-mono text-fs-64 font-semibold leading-none tabular-nums text-ink">
            {currentPct === null ? "—" : Math.round(currentPct)}
          </span>
          <span className="font-mono text-fs-16 uppercase tracking-cap-narrow text-ink-3">
            %
          </span>
        </p>
        <p className="flex items-center gap-2 font-mono text-fs-11 text-ink-2">
          <span aria-hidden="true" className={dotClass}>
            ●
          </span>
          <span>{statusText}</span>
        </p>
      </div>
      <div className="flex flex-col justify-center gap-2">
        <svg
          aria-label="moisture band"
          role="img"
          viewBox="0 0 100 32"
          preserveAspectRatio="none"
          className="h-10 w-full"
        >
          <title>
            {hasTarget ? `Target band ${lo}-${hi}%` : "Target unavailable"} · current{" "}
            {currentPct === null ? "—" : Math.round(currentPct)}%
          </title>
          {/* Base rule running across the track. */}
          <line
            x1="0"
            y1="10"
            x2="100"
            y2="10"
            className="stroke-rule-strong"
            strokeWidth="0.4"
          />
          {/* Target-band tint. */}
          {hasTarget ? (
            <rect
              x={bandX}
              y="6"
              width={bandW}
              height="8"
              className="fill-sensor-vpd opacity-30"
            />
          ) : null}
          {/* Marker line + dot. */}
          {currentPct !== null ? (
            <>
              <line
                x1={markerX}
                y1="3"
                x2={markerX}
                y2="17"
                className="stroke-accent-magenta"
                strokeWidth="0.8"
              />
              <circle cx={markerX} cy="10" r="2" className="fill-accent-magenta" />
            </>
          ) : null}
          {/* Tick labels — SVG text avoids HTML inline-style attrs. */}
          {TRACK_TICKS.map((tick) => (
            <text
              key={tick}
              x={pctFraction(tick)}
              y="28"
              textAnchor="middle"
              className="fill-ink-3 font-mono text-fs-6"
            >
              {tick}
            </text>
          ))}
        </svg>
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          {hasTarget ? `target ${lo}-${hi}%` : "target unavailable"}
        </p>
      </div>
    </section>
  );
}

// Normalized viewBox mirrors ui/Sparkline.tsx so the crosshair / area-fill
// treatment reads identically in the drawer. vector-effect=non-scaling-stroke
// keeps strokes crisp when the svg is stretched to h-20 w-full.
const CHART_VB_W = 100;
const CHART_VB_H = 30;

function MoistureChart({
  points,
  stickerColor,
  hoverIndex,
  onHoverIndex,
}: {
  points: readonly MoistureHistoryPoint[];
  stickerColor: StickerColor;
  hoverIndex: number | null;
  onHoverIndex: (index: number | null) => void;
}): ReactNode {
  if (points.length === 0) return null;
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = points.length === 1 ? 0 : CHART_VB_W / (points.length - 1);
  const xFor = (i: number): number =>
    points.length === 1 ? CHART_VB_W / 2 : i * stepX;
  const yFor = (v: number): number => CHART_VB_H - ((v - min) / range) * CHART_VB_H;

  const linePath = points
    .map((p, i) => {
      const cmd = i === 0 ? "M" : "L";
      return `${cmd} ${xFor(i).toFixed(2)} ${yFor(p.value).toFixed(2)}`;
    })
    .join(" ");
  const areaPath = `${linePath} L ${CHART_VB_W.toFixed(2)} ${CHART_VB_H} L 0 ${CHART_VB_H} Z`;

  const handleMove = (event: React.PointerEvent<SVGSVGElement>): void => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (rect.width <= 0) {
      onHoverIndex(null);
      return;
    }
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    onHoverIndex(Math.round(ratio * (points.length - 1)));
  };

  const clampedHover =
    hoverIndex === null ? null : Math.max(0, Math.min(points.length - 1, hoverIndex));
  const hovered = clampedHover === null ? null : (points[clampedHover] ?? null);
  const hoverX = clampedHover === null ? null : xFor(clampedHover);
  const hoverY = hovered ? yFor(hovered.value) : null;
  const hoverRatio =
    clampedHover === null ? null : clampedHover / (points.length - 1 || 1);

  return (
    <div className="relative cursor-crosshair">
      <svg
        aria-label="moisture history"
        role="img"
        viewBox={`0 0 ${CHART_VB_W} ${CHART_VB_H}`}
        preserveAspectRatio="none"
        className="block h-20 w-full"
        fill="none"
        onPointerMove={handleMove}
        onPointerLeave={() => {
          onHoverIndex(null);
        }}
      >
        <path d={areaPath} className={STICKER_FILL[stickerColor]} opacity="0.1" />
        <path
          d={linePath}
          className={STICKER_STROKE[stickerColor]}
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
              y2={CHART_VB_H}
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
              className={`${STICKER_FILL[stickerColor]} stroke-paper`}
              strokeWidth="0.5"
              vectorEffect="non-scaling-stroke"
            />
          </g>
        ) : null}
      </svg>
      {hovered !== null && hoverRatio !== null ? (
        <span
          role="tooltip"
          // eslint-disable-next-line no-restricted-syntax -- runtime-computed hover position; not expressible in build-time Tailwind classes
          style={{ left: `${hoverRatio * 100}%` }}
          className="pointer-events-none absolute -top-3.5 -translate-x-1/2 whitespace-nowrap border border-rule-strong bg-paper px-1.5 py-px font-mono text-fs-10 tabular-nums text-ink"
        >
          {Math.round(hovered.value)}%
        </span>
      ) : null}
    </div>
  );
}

export function PlantDetail({
  payload,
  moistureHistory,
  moistureRange,
  onMoistureRangeChange,
  onClose,
}: PlantDetailProps): ReactNode {
  const dialogRef = useRef<HTMLElement | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  // Imperative focus-on-mount so ESC + screen-reader pickup work
  // without an extra click.
  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  const target = payload.moisture.target;
  const bandTarget: readonly [number, number] | null =
    target && target.length >= 2 ? [target[0] as number, target[1] as number] : null;

  return (
    <>
      {/* Scrim — click anywhere to close; animated fade-in. */}
      <button
        type="button"
        aria-label="Close plant detail"
        tabIndex={-1}
        onClick={onClose}
        className="fixed inset-0 z-40 animate-pd-fade cursor-default bg-scrim-55 backdrop-blur-sm"
      />
      <aside
        ref={dialogRef}
        role="dialog"
        aria-label="Plant detail"
        aria-modal="true"
        tabIndex={-1}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.preventDefault();
            onClose();
          }
        }}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-180 animate-pd-slide flex-col gap-5 overflow-y-auto border-l border-ink bg-paper px-8 pb-10 pt-7"
      >
        <header className="flex flex-col gap-1 border-b border-rule-strong pb-3">
          <div className="flex items-center gap-3">
            <span
              role="img"
              aria-label="sticker"
              data-color={payload.sticker_color}
              className={`inline-block h-3.5 w-3.5 border border-ink ${STICKER_BG[payload.sticker_color]}`}
            />
            <h2 className="font-sans text-fs-28 font-semibold tracking-tighter text-ink">
              {payload.name}
            </h2>
            <span
              className={`border px-1.75 py-0.75 font-mono text-fs-9 uppercase tracking-cap-med ${STATUS_TAG_TONE[payload.status]}`}
            >
              {STATUS_TAG_LABEL[payload.status]}
            </span>
            <span role="status" aria-label="Plant status" className="sr-only">
              {STATUS_LABEL[payload.status]}
            </span>
            <button
              type="button"
              onClick={onClose}
              className="ml-auto border border-rule-strong px-2.5 py-0.75 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition hover:border-ink-2 hover:text-ink"
            >
              close ✕
            </button>
          </div>
          <p className="font-serif text-fs-15 italic text-ink-3">{payload.label}</p>
        </header>

        <MoistureHero currentPct={payload.moisture.current_pct} target={bandTarget} />

        <section className="flex flex-col gap-2">
          <header className="flex items-baseline justify-between gap-3">
            <h3 className="font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
              Soil moisture · {RANGE_LABEL[moistureRange]}
            </h3>
            <div className="flex items-baseline gap-3">
              <HoverTimestamp
                hoverIndex={hoverIndex}
                points={moistureHistory}
                className="font-mono text-fs-10 tabular-nums text-ink-2"
              />
              <RangeSwitch value={moistureRange} onChange={onMoistureRangeChange} />
            </div>
          </header>
          <MoistureChart
            points={moistureHistory}
            stickerColor={payload.sticker_color}
            hoverIndex={hoverIndex}
            onHoverIndex={setHoverIndex}
          />
        </section>

        <section aria-label="Timeline" className="flex flex-col gap-2">
          <h3 className="font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
            Timeline
          </h3>
          <ul aria-label="timeline entries" className="flex flex-col">
            {payload.timeline.map((entry) => {
              const highlightRow = entry.highlight
                ? "border-l-2 border-accent-magenta bg-accent-magenta/[0.04] pl-3"
                : "border-l-2 border-transparent pl-3";
              return (
                <li
                  key={`${entry.date}-${entry.day}-${entry.text}`}
                  aria-label="timeline entry"
                  className={`grid grid-cols-[100px_40px_1fr] items-baseline gap-3 border-b border-rule py-2 last:border-b-0 ${highlightRow}`}
                >
                  <span className="font-mono text-fs-10 uppercase tracking-cap-narrow text-ink-3">
                    {entry.date}
                  </span>
                  <span className="font-mono text-fs-10 uppercase tracking-cap-narrow text-ink-2">
                    d{entry.day}
                  </span>
                  <span
                    className={`font-sans text-fs-13 leading-prose ${
                      entry.highlight ? "text-ink" : "text-ink-2"
                    }`}
                  >
                    <Markdown components={INLINE_MARKDOWN_COMPONENTS}>
                      {entry.text}
                    </Markdown>
                  </span>
                </li>
              );
            })}
          </ul>
        </section>

        {payload.note !== null ? (
          <section
            aria-label="Note"
            className="border-l-2 border-accent-purple bg-paper-2 px-4 py-3"
          >
            <p className="font-serif text-fs-15 italic leading-ui text-ink-2">
              <Markdown components={INLINE_MARKDOWN_COMPONENTS}>
                {payload.note.text}
              </Markdown>
            </p>
            <p className="mt-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              — current status · updated {payload.note.updated}
            </p>
          </section>
        ) : null}

        <footer className="mt-auto flex items-center justify-between border-t border-rule-strong pt-3 font-mono text-fs-10 uppercase tracking-cap-narrow text-ink-3">
          <span>→ {payload.wiki_path}</span>
        </footer>
      </aside>
    </>
  );
}
