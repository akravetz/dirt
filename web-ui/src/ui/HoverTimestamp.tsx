// Shared "timestamp of the hovered bucket" rendered in a section header
// while a sparkline/chart is being hovered. Used by both the dashboard
// history grid (all five sparklines share one hoverIndex) and the
// plant-detail moisture chart (single chart, scoped hoverIndex).
//
// Returns null when no bucket is hovered or the timestamp is missing /
// unparseable — callers don't need to guard.
import type { ReactNode } from "react";

const HOVER_TS_FMT = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

interface HoverTimestampProps {
  hoverIndex: number | null;
  points: readonly { ts: string }[];
  className?: string;
}

export function HoverTimestamp({
  hoverIndex,
  points,
  className = "font-mono text-fs-11 tabular-nums text-ink-2",
}: HoverTimestampProps): ReactNode {
  if (hoverIndex === null || points.length === 0) return null;
  const clamped = Math.max(0, Math.min(points.length - 1, hoverIndex));
  const ts = points[clamped]?.ts;
  if (!ts) return null;
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return null;
  return <span className={className}>{HOVER_TS_FMT.format(date)}</span>;
}
