import type { ReactNode } from "react";

const HOVER_TIMESTAMP_FORMAT = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function HoverTimestamp({
  className = "font-mono text-fs-11 tabular-nums text-ink-2",
  timestamp,
}: {
  className?: string;
  timestamp: string | null;
}): ReactNode {
  if (timestamp === null) return null;
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return null;
  return <span className={className}>{HOVER_TIMESTAMP_FORMAT.format(date)}</span>;
}
