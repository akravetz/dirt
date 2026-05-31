import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { PlantSticker } from "./PlantSticker";

export type MoistureComparisonPoint = {
  ts: string;
  value: number | null;
};

export type MoistureComparisonSeries = {
  plantId: string;
  name: string;
  stickerColor: string | null;
  latestValue: number | null;
  points: readonly MoistureComparisonPoint[];
};

type AlignedSeries = MoistureComparisonSeries & {
  alignedPoints: readonly MoistureComparisonPoint[];
  lineClass: string;
};

type PathPoint = {
  x: number;
  y: number;
};

type PathSegment = {
  key: string;
  linePath: string;
};

type MoistureComparisonChartProps = {
  emptyLabel?: string;
  hoverIndex: number | null;
  onHoverIndex: (index: number | null) => void;
  onHoverTimestamp?: (timestamp: string | null) => void;
  selectedPlantId: string;
  series: readonly MoistureComparisonSeries[];
  unit: string;
};

const VIEWBOX_W = 100;
const VIEWBOX_H = 44;
const LINE_BY_STICKER: Record<string, string> = {
  yellow: "stroke-sticker-yellow",
  orange: "stroke-sticker-orange",
  pink: "stroke-sticker-pink",
  blue: "stroke-sticker-blue",
};
const FALLBACK_LINE_CLASSES = [
  "stroke-leaf",
  "stroke-sensor-vpd",
  "stroke-accent-purple",
  "stroke-sensor-reservoir",
] as const;

export function MoistureComparisonChart({
  emptyLabel = "No moisture history for this range",
  hoverIndex,
  onHoverIndex,
  onHoverTimestamp,
  selectedPlantId,
  series,
  unit,
}: MoistureComparisonChartProps): ReactNode {
  const [hiddenPlantIds, setHiddenPlantIds] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  const axis = useMemo(() => buildAxis(series), [series]);
  const alignedSeries = useMemo(
    () => alignSeries(series, axis, selectedPlantId),
    [axis, selectedPlantId, series],
  );
  const visibleSeries = alignedSeries.filter(
    (plant) => plant.plantId === selectedPlantId || !hiddenPlantIds.has(plant.plantId),
  );
  const drawSeries = [...visibleSeries].sort(
    (a, b) =>
      Number(a.plantId === selectedPlantId) - Number(b.plantId === selectedPlantId),
  );

  if (series.length === 0) {
    return (
      <article
        aria-label="Plant moisture comparison chart"
        className="flex flex-col gap-3 bg-paper-2 px-3.5 py-3"
      >
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          {emptyLabel}
        </p>
      </article>
    );
  }

  const hasValues = visibleSeries.some((plant) =>
    plant.alignedPoints.some((point) => point.value !== null),
  );
  if (axis.length === 0 || !hasValues) {
    return (
      <article
        aria-label="Plant moisture comparison chart"
        className="flex flex-col gap-3 bg-paper-2 px-3.5 py-3"
      >
        <MoistureLegend
          hiddenPlantIds={hiddenPlantIds}
          onToggle={setHiddenPlantIds}
          selectedPlantId={selectedPlantId}
          series={alignedSeries}
        />
        <div className="flex h-42 items-center border border-dashed border-rule px-3">
          <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            {emptyLabel}
          </p>
        </div>
      </article>
    );
  }

  const stepX = axis.length === 1 ? 0 : VIEWBOX_W / (axis.length - 1);
  const xFor = (index: number): number =>
    axis.length === 1 ? VIEWBOX_W / 2 : index * stepX;
  const yFor = (value: number): number =>
    VIEWBOX_H - (Math.max(0, Math.min(100, value)) / 100) * VIEWBOX_H;
  const clampedHover =
    hoverIndex === null ? null : Math.max(0, Math.min(axis.length - 1, hoverIndex));
  const hoverX = clampedHover === null ? null : xFor(clampedHover);
  const hoverRatio =
    clampedHover === null ? null : clampedHover / (axis.length - 1 || 1);
  const tooltipRows =
    clampedHover === null
      ? []
      : visibleSeries.flatMap((plant) => {
          const value = plant.alignedPoints[clampedHover]?.value;
          return value === undefined || value === null ? [] : [{ plant, value }];
        });

  const handlePointerPosition = (event: React.PointerEvent<SVGSVGElement>): void => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (rect.width <= 0) {
      onHoverIndex(null);
      onHoverTimestamp?.(null);
      return;
    }
    const relX = event.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, relX / rect.width));
    const index = Math.round(ratio * (axis.length - 1));
    onHoverIndex(index);
    onHoverTimestamp?.(axis[index] ?? null);
  };

  const handlePointerDown = (event: React.PointerEvent<SVGSVGElement>): void => {
    if (event.pointerType === "touch") {
      event.preventDefault();
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    handlePointerPosition(event);
  };

  const handlePointerUp = (event: React.PointerEvent<SVGSVGElement>): void => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const handlePointerLeave = (event: React.PointerEvent<SVGSVGElement>): void => {
    if (event.pointerType === "touch") {
      return;
    }
    onHoverIndex(null);
    onHoverTimestamp?.(null);
  };

  return (
    <article
      aria-label="Plant moisture comparison chart"
      className="flex flex-col gap-3 bg-paper-2 px-3.5 py-3"
    >
      <MoistureLegend
        hiddenPlantIds={hiddenPlantIds}
        onToggle={setHiddenPlantIds}
        selectedPlantId={selectedPlantId}
        series={alignedSeries}
      />
      <div className="grid grid-cols-[2.5rem_1fr] gap-2">
        <div className="flex h-42 flex-col justify-between py-1 text-right font-mono text-fs-10 tabular-nums text-ink-3">
          <span>100%</span>
          <span>50%</span>
          <span>0%</span>
        </div>
        <div className="relative min-w-0 cursor-crosshair border border-rule bg-paper">
          <svg
            aria-label="plant moisture comparison"
            role="img"
            viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
            preserveAspectRatio="none"
            className="block h-42 w-full touch-none select-none"
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerPosition}
            onPointerUp={handlePointerUp}
            onPointerCancel={handlePointerUp}
            onPointerLeave={handlePointerLeave}
          >
            <title>Plant moisture comparison</title>
            <line
              x1="0"
              y1={yFor(50)}
              x2={VIEWBOX_W}
              y2={yFor(50)}
              className="stroke-rule"
              strokeWidth="0.4"
              vectorEffect="non-scaling-stroke"
            />
            {drawSeries.map((plant) =>
              buildPathSegments(plant.alignedPoints, xFor, yFor).map((segment) => (
                <path
                  key={`${plant.plantId}-${segment.key}`}
                  d={segment.linePath}
                  className={
                    plant.plantId === selectedPlantId
                      ? "stroke-sensor-moisture"
                      : plant.lineClass
                  }
                  fill="none"
                  opacity={plant.plantId === selectedPlantId ? "1" : "0.6"}
                  strokeWidth={plant.plantId === selectedPlantId ? "1.4" : "0.9"}
                  vectorEffect="non-scaling-stroke"
                />
              )),
            )}
            {hoverX !== null ? (
              <g aria-label="crosshair">
                <line
                  x1={hoverX}
                  y1="0"
                  x2={hoverX}
                  y2={VIEWBOX_H}
                  className="stroke-ink"
                  strokeWidth="0.4"
                  strokeDasharray="1 1"
                  vectorEffect="non-scaling-stroke"
                  opacity="0.55"
                />
              </g>
            ) : null}
          </svg>
          {tooltipRows.length > 0 && hoverRatio !== null ? (
            <div
              role="tooltip"
              data-hover-index={clampedHover ?? undefined}
              // eslint-disable-next-line no-restricted-syntax -- runtime-computed hover position; not expressible in build-time Tailwind classes
              style={{ left: `${hoverRatio * 100}%` }}
              className="pointer-events-none absolute top-2 max-w-52 -translate-x-1/2 border border-rule-strong bg-paper px-2 py-1 font-mono text-fs-10 tabular-nums text-ink shadow-sm"
            >
              {tooltipRows.map(({ plant, value }) => (
                <div
                  key={plant.plantId}
                  className="flex items-center justify-between gap-3"
                >
                  <span className="truncate text-ink-3">{plant.name}</span>
                  <span>{formatMoisture(value, unit)}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function MoistureLegend({
  hiddenPlantIds,
  onToggle,
  selectedPlantId,
  series,
}: {
  hiddenPlantIds: ReadonlySet<string>;
  onToggle: (hiddenPlantIds: ReadonlySet<string>) => void;
  selectedPlantId: string;
  series: readonly AlignedSeries[];
}): ReactNode {
  return (
    <div className="flex flex-wrap gap-2">
      {series.map((plant) => {
        const isSelected = plant.plantId === selectedPlantId;
        const isVisible = isSelected || !hiddenPlantIds.has(plant.plantId);
        return (
          <button
            key={plant.plantId}
            type="button"
            disabled={isSelected}
            aria-pressed={isVisible}
            onClick={() => {
              if (isSelected) return;
              const next = new Set(hiddenPlantIds);
              if (next.has(plant.plantId)) {
                next.delete(plant.plantId);
              } else {
                next.add(plant.plantId);
              }
              onToggle(next);
            }}
            className={
              isVisible
                ? "inline-flex min-w-0 items-center gap-2 border border-rule-strong bg-paper px-2.5 py-1.5 text-left text-fs-11 text-ink"
                : "inline-flex min-w-0 items-center gap-2 border border-rule bg-paper-2 px-2.5 py-1.5 text-left text-fs-11 text-ink-3 opacity-70"
            }
          >
            <PlantSticker color={plant.stickerColor} size="sm" />
            <span className="truncate font-sans">{plant.name}</span>
            {isSelected ? (
              <span className="font-mono text-fs-10 uppercase tracking-caps text-sensor-moisture">
                Selected
              </span>
            ) : null}
            <span className="font-mono text-fs-10 tabular-nums text-ink-3">
              {plant.latestValue === null
                ? "No reading"
                : formatMoisture(plant.latestValue, "%")}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function buildAxis(series: readonly MoistureComparisonSeries[]): string[] {
  const timestamps = new Set<string>();
  for (const plant of series) {
    for (const point of plant.points) {
      timestamps.add(point.ts);
    }
  }
  return [...timestamps].sort(compareIsoTimestamps);
}

function compareIsoTimestamps(a: string, b: string): number {
  return new Date(a).getTime() - new Date(b).getTime();
}

function alignSeries(
  series: readonly MoistureComparisonSeries[],
  axis: readonly string[],
  selectedPlantId: string,
): AlignedSeries[] {
  return series.map((plant, index) => {
    const valuesByTimestamp = new Map(
      plant.points.map((point) => [point.ts, point.value]),
    );
    const lineClass =
      (plant.stickerColor === null ? undefined : LINE_BY_STICKER[plant.stickerColor]) ??
      FALLBACK_LINE_CLASSES[index % FALLBACK_LINE_CLASSES.length] ??
      "stroke-ink";
    return {
      ...plant,
      alignedPoints: axis.map((ts) => ({
        ts,
        value: valuesByTimestamp.get(ts) ?? null,
      })),
      lineClass:
        plant.plantId === selectedPlantId ? "stroke-sensor-moisture" : lineClass,
    };
  });
}

function buildPathSegments(
  points: readonly MoistureComparisonPoint[],
  xFor: (index: number) => number,
  yFor: (value: number) => number,
): PathSegment[] {
  const segments: PathSegment[] = [];
  let current: PathPoint[] = [];
  let startIndex = 0;

  const flush = (endIndex: number): void => {
    if (current.length === 0) return;
    const linePath = current
      .map(
        (point, index) =>
          `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`,
      )
      .join(" ");
    segments.push({ key: `${startIndex}-${endIndex}`, linePath });
    current = [];
  };

  points.forEach((point, index) => {
    if (point.value === null) {
      flush(index - 1);
      return;
    }
    if (current.length === 0) {
      startIndex = index;
    }
    current.push({ x: xFor(index), y: yFor(point.value) });
  });
  flush(points.length - 1);

  return segments;
}

function formatMoisture(value: number, unit: string): string {
  if (unit === "%") return `${Math.round(value)}%`;
  return `${value.toFixed(1)}${unit}`;
}
