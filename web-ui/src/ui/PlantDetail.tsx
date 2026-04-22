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
import { useEffect, useRef } from "react";
import Markdown from "react-markdown";
import {
  type PlantCode,
  STICKER_BG,
  STICKER_STROKE,
  type StickerColor,
} from "@/ui/plant-types";

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
  irrigationEvents24h: number;
  onClose: () => void;
}

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
  const [lo, hi] = target ?? [55, 70];
  const pct = currentPct ?? lo;
  const pctFraction = (x: number): number =>
    ((x - TRACK_MIN) / (TRACK_MAX - TRACK_MIN)) * 100;
  const bandX = pctFraction(lo);
  const bandW = pctFraction(hi) - bandX;
  const markerX = pctFraction(Math.max(TRACK_MIN, Math.min(TRACK_MAX, pct)));
  const statusText =
    currentPct === null
      ? "No reading"
      : currentPct < lo
        ? "below target — irrigation due"
        : currentPct > hi
          ? "above target — drying down"
          : "in target band";
  const dotClass =
    currentPct !== null && currentPct >= lo && currentPct <= hi
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
            Target band {lo}–{hi}% · current{" "}
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
          <rect
            x={bandX}
            y="6"
            width={bandW}
            height="8"
            className="fill-sensor-vpd opacity-30"
          />
          {/* Marker line + dot. */}
          <line
            x1={markerX}
            y1="3"
            x2={markerX}
            y2="17"
            className="stroke-accent-magenta"
            strokeWidth="0.8"
          />
          <circle cx={markerX} cy="10" r="2" className="fill-accent-magenta" />
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
          target {lo}–{hi}%
        </p>
      </div>
    </section>
  );
}

// SVG chart dimensions chosen to read like the band in
// docs/plans/refs/plant-detail-a.png.
const CHART_W = 480;
const CHART_H = 80;

function MoistureChart({
  points,
  stickerColor,
}: {
  points: readonly MoistureHistoryPoint[];
  stickerColor: StickerColor;
}): ReactNode {
  if (points.length === 0) return null;
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const n = points.length;
  const path = points
    .map((p, i) => {
      const x = (i / Math.max(n - 1, 1)) * CHART_W;
      const y = CHART_H - ((p.value - min) / range) * CHART_H;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      aria-label="moisture history"
      role="img"
      viewBox={`0 0 ${CHART_W} ${CHART_H}`}
      preserveAspectRatio="none"
      className="h-20 w-full"
      fill="none"
    >
      <title>24h soil moisture</title>
      <path d={path} className={STICKER_STROKE[stickerColor]} strokeWidth="1.5" />
    </svg>
  );
}

export function PlantDetail({
  payload,
  moistureHistory,
  irrigationEvents24h,
  onClose,
}: PlantDetailProps): ReactNode {
  const dialogRef = useRef<HTMLElement | null>(null);
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
          <header className="flex items-baseline justify-between">
            <h3 className="font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
              Soil moisture · last 24h
            </h3>
            <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              {irrigationEvents24h} irrigation
            </span>
          </header>
          <MoistureChart
            points={moistureHistory}
            stickerColor={payload.sticker_color}
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
                  key={entry.date}
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
          <span>→ live · preset plant_{payload.code}</span>
        </footer>
      </aside>
    </>
  );
}
