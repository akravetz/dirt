// Plant-detail drawer — overlays the dashboard when a plant is selected.
//
// ARIA contract the e2e spec relies on:
//   - aside[role=dialog][aria-label="Plant detail"] — spec asserts via
//                                                     getByRole("dialog").
//   - ESC triggers onClose via onKeyDown (scoped to the rendered dialog
//     so the handler doesn't leak across routes, unlike a
//     document-level listener).
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
// strip the paragraph wrapper to keep the markdown inline and preserve
// the existing Tailwind typography classes on the surrounding element.
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

// SVG chart dimensions chosen to read like the band in
// docs/plans/refs/plant-detail-a.png. Same viewBox-scaling trick as
// PlantCard avoids TS-16 inline-style rules (SVG attrs aren't styles).
const CHART_W = 480;
const CHART_H = 80;

const STATUS_LABEL: Record<PlantDetailPayload["status"], string> = {
  primary: "Primary",
  secondary: "Secondary",
  retired: "Retired",
};

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
  // without an extra click. Autofocus on <aside> is non-standard.
  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  const target = payload.moisture.target;
  const targetLabel =
    target && target.length >= 2 ? `target ${target[0]}–${target[1]}%` : "no target";
  const moistureLabel =
    payload.moisture.current_pct === null
      ? "—"
      : `${Math.round(payload.moisture.current_pct)}`;

  return (
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
      className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col gap-4 overflow-y-auto border-l border-rule bg-paper p-6 shadow-xl"
    >
      <header className="flex items-baseline gap-3 border-b border-rule pb-3">
        <span
          role="img"
          aria-label="sticker"
          data-color={payload.sticker_color}
          className={`inline-block h-4 w-4 ${STICKER_BG[payload.sticker_color]}`}
        />
        <h2 className="font-serif text-2xl italic text-ink">{payload.name}</h2>
        <span
          role="status"
          aria-label="Plant status"
          className="font-mono text-xs uppercase tracking-caps text-ink-2"
        >
          {STATUS_LABEL[payload.status]}
        </span>
        <span className="ml-auto font-mono text-xs uppercase tracking-caps text-ink-3">
          {payload.label}
        </span>
      </header>
      <section aria-label="Moisture" className="flex flex-col gap-2">
        <header className="flex items-baseline justify-between">
          <h3 className="font-mono text-xs uppercase tracking-caps text-ink-2">
            Soil moisture · last 24h
          </h3>
          <span className="font-mono text-xs uppercase tracking-caps text-ink-3">
            {irrigationEvents24h} irrigation
          </span>
        </header>
        <p className="flex items-baseline gap-2">
          <span className="font-serif text-5xl italic text-ink">{moistureLabel}</span>
          <span className="font-mono text-xs uppercase tracking-caps text-ink-3">
            %
          </span>
          <span className="ml-3 font-mono text-xs uppercase tracking-caps text-ink-3">
            {targetLabel}
          </span>
        </p>
        <MoistureChart points={moistureHistory} stickerColor={payload.sticker_color} />
      </section>
      <section aria-label="Timeline" className="flex flex-col gap-2">
        <h3 className="font-mono text-xs uppercase tracking-caps text-ink-2">
          Timeline
        </h3>
        <ul aria-label="timeline entries" className="flex flex-col">
          {payload.timeline.map((entry) => (
            <li
              key={entry.date}
              aria-label="timeline entry"
              className="flex items-baseline gap-3 border-b border-rule py-2 last:border-b-0"
            >
              <span className="font-mono text-xs uppercase tracking-caps text-ink-3">
                {entry.date}
              </span>
              <span className="font-mono text-xs uppercase tracking-caps text-ink-2">
                d{entry.day}
              </span>
              <span
                className={`font-sans text-sm ${
                  entry.highlight ? "text-ink" : "text-ink-2"
                }`}
              >
                <Markdown components={INLINE_MARKDOWN_COMPONENTS}>
                  {entry.text}
                </Markdown>
              </span>
            </li>
          ))}
        </ul>
      </section>
      {payload.note !== null ? (
        <section aria-label="Note" className="flex flex-col gap-1">
          <h3 className="font-mono text-xs uppercase tracking-caps text-ink-2">
            Current status · updated {payload.note.updated}
          </h3>
          <p className="font-serif text-base italic text-ink">
            <Markdown components={INLINE_MARKDOWN_COMPONENTS}>
              {payload.note.text}
            </Markdown>
          </p>
        </section>
      ) : null}
      <footer className="mt-auto flex items-center justify-between border-t border-rule pt-3">
        <span className="font-mono text-xs uppercase tracking-caps text-ink-3">
          {payload.wiki_path}
        </span>
        <button
          type="button"
          onClick={onClose}
          className="border border-rule bg-paper px-3 py-1 font-mono text-xs uppercase tracking-caps text-ink-2 hover:border-rule-strong"
        >
          Close
        </button>
      </footer>
    </aside>
  );
}
