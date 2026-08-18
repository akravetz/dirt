import { type PointerEvent, type ReactNode, useMemo } from "react";
import {
  alignHistoryPoints,
  type HistoryBucket,
  type HistoryPoint,
  historyTimestampAxis,
  type PlantSeriesColor,
} from "@/shared/historySeries";
import { formatMetricDisplayValue } from "@/shared/metricFormat";
import type { SensorAccent } from "@/shared/metricPresentation";

export type SparklineColor = SensorAccent | PlantSeriesColor;

export type SparklineSeries = {
  color: SparklineColor;
  id: string;
  label: string;
  points: readonly HistoryPoint[];
};

type SparklineProps = {
  /** Rollup cadence used to retain missing buckets as explicit gaps. */
  bucket?: HistoryBucket;
  /** Full-card chrome for standalone metric tiles; grid keeps dashboard borders. */
  chrome?: "grid" | "card";
  /** Message shown when the selected range has no values. */
  emptyLabel?: string;
  /** Timestamp shared across related history charts; null means no crosshair. */
  hoverTimestamp: string | null;
  /** Metric display name; the article's accessible name and heading text. */
  name: string;
  /** Called with the nearest real bucket timestamp under the pointer. */
  onHoverTimestamp: (timestamp: string | null) => void;
  /** One or more independently identified timestamped histories. */
  series: readonly SparklineSeries[];
  /** Optional metric metadata rendered between the heading and chart. */
  summary?: ReactNode;
  /** Unit string shared by every series in this metric chart. */
  unit: string;
  /** Number of decimal places requested by metric presentation. */
  valuePrecision?: number;
  /** Optional fixed y-axis domain. */
  yMax?: number;
  yMin?: number;
};

const COLOR_CLASSES = {
  temp: {
    fill: "fill-sensor-temp",
    stroke: "stroke-sensor-temp",
    text: "text-sensor-temp",
  },
  humidity: {
    fill: "fill-sensor-humidity",
    stroke: "stroke-sensor-humidity",
    text: "text-sensor-humidity",
  },
  vpd: {
    fill: "fill-sensor-vpd",
    stroke: "stroke-sensor-vpd",
    text: "text-sensor-vpd",
  },
  moisture: {
    fill: "fill-sensor-moisture",
    stroke: "stroke-sensor-moisture",
    text: "text-sensor-moisture",
  },
  reservoir: {
    fill: "fill-sensor-reservoir",
    stroke: "stroke-sensor-reservoir",
    text: "text-sensor-reservoir",
  },
  neutral: { fill: "fill-ink", stroke: "stroke-ink", text: "text-ink" },
  "plant-a": {
    fill: "fill-plant-a",
    stroke: "stroke-plant-a",
    text: "text-plant-a",
  },
  "plant-b": {
    fill: "fill-plant-b",
    stroke: "stroke-plant-b",
    text: "text-plant-b",
  },
  "plant-c": {
    fill: "fill-plant-c",
    stroke: "stroke-plant-c",
    text: "text-plant-c",
  },
  "plant-d": {
    fill: "fill-plant-d",
    stroke: "stroke-plant-d",
    text: "text-plant-d",
  },
} satisfies Record<SparklineColor, { fill: string; stroke: string; text: string }>;

const VIEWBOX_W = 100;
const VIEWBOX_H = 30;

export function Sparkline({
  bucket,
  chrome = "grid",
  emptyLabel = "No data for this range",
  hoverTimestamp,
  name,
  onHoverTimestamp,
  series,
  summary,
  unit,
  valuePrecision = 1,
  yMax,
  yMin,
}: SparklineProps): ReactNode {
  const articleClass =
    chrome === "card"
      ? "flex flex-col gap-2 border border-rule-strong bg-paper-2 px-3.5 py-3"
      : "flex flex-col gap-2 border-b border-r border-rule bg-paper-2 px-3.5 py-3";
  const headerColor = COLOR_CLASSES[series[0]?.color ?? "neutral"].text;
  const chartData = useMemo(
    () => ({
      axis: historyTimestampAxis(
        series.map((item) => item.points),
        bucket,
      ),
      values: series.flatMap((item) =>
        item.points.flatMap((point) => (point.value === null ? [] : [point.value])),
      ),
    }),
    [bucket, series],
  );
  const yDomain = {
    ...(yMin === undefined ? {} : { yMin }),
    ...(yMax === undefined ? {} : { yMax }),
  };

  return (
    <article aria-label={`${name} sparkline`} className={articleClass}>
      <header className="flex items-center gap-2 font-sans text-fs-11 font-medium text-ink-2">
        <span aria-hidden="true" className={headerColor}>
          ◆
        </span>
        <span>{name}</span>
      </header>
      {summary}
      {series.length > 1 ? <SparklineLegend series={series} /> : null}
      {chartData.axis.length === 0 || chartData.values.length === 0 ? (
        <div className="flex h-10 items-center border border-dashed border-rule px-2">
          <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            {emptyLabel}
          </p>
        </div>
      ) : (
        <SparklinePlot
          axis={chartData.axis}
          hoverTimestamp={hoverTimestamp}
          name={name}
          onHoverTimestamp={onHoverTimestamp}
          series={series}
          unit={unit}
          valuePrecision={valuePrecision}
          values={chartData.values}
          {...yDomain}
        />
      )}
    </article>
  );
}

function SparklineLegend({
  series,
}: {
  series: readonly SparklineSeries[];
}): ReactNode {
  return (
    <ul aria-label="Series legend" className="flex flex-wrap gap-x-3 gap-y-1">
      {series.map((item) => (
        <li
          key={item.id}
          className="inline-flex min-w-0 items-center gap-1.5 font-mono text-fs-9 uppercase tracking-caps text-ink-3"
        >
          <span
            aria-hidden="true"
            className={`h-1.5 w-1.5 ${COLOR_CLASSES[item.color].fill}`}
          />
          <span className="truncate">{item.label}</span>
        </li>
      ))}
    </ul>
  );
}

function SparklinePlot({
  axis,
  hoverTimestamp,
  name,
  onHoverTimestamp,
  series,
  unit,
  valuePrecision,
  values,
  yMax,
  yMin,
}: {
  axis: readonly string[];
  hoverTimestamp: string | null;
  name: string;
  onHoverTimestamp: (timestamp: string | null) => void;
  series: readonly SparklineSeries[];
  unit: string;
  valuePrecision: number;
  values: readonly number[];
  yMax?: number;
  yMin?: number;
}): ReactNode {
  const geometry = useMemo(() => {
    const hasFixedDomain = yMin !== undefined && yMax !== undefined && yMax > yMin;
    const min = hasFixedDomain && yMin !== undefined ? yMin : Math.min(...values);
    const max = hasFixedDomain && yMax !== undefined ? yMax : Math.max(...values);
    const range = max - min || 1;
    const stepX = axis.length === 1 ? 0 : VIEWBOX_W / (axis.length - 1);
    const xFor = (index: number): number =>
      axis.length === 1 ? VIEWBOX_W / 2 : index * stepX;
    const yFor = (value: number): number => {
      const clamped = hasFixedDomain ? Math.max(min, Math.min(max, value)) : value;
      return VIEWBOX_H - ((clamped - min) / range) * VIEWBOX_H;
    };
    const plottedSeries = series.map((item) => {
      const alignedPoints = alignHistoryPoints(item.points, axis);
      return {
        ...item,
        alignedPoints,
        paths: buildPathSegments(alignedPoints, xFor, yFor),
      };
    });
    return { plottedSeries, xFor, yFor };
  }, [axis, series, values, yMax, yMin]);
  const { plottedSeries, xFor, yFor } = geometry;
  const hoverAxisIndex = hoverTimestamp === null ? -1 : axis.indexOf(hoverTimestamp);
  const hoverX = hoverAxisIndex < 0 ? null : xFor(hoverAxisIndex);
  const hoveredValues =
    hoverAxisIndex < 0
      ? []
      : plottedSeries.flatMap((item) => {
          const point = item.alignedPoints[hoverAxisIndex];
          return point?.value === null || point?.value === undefined
            ? []
            : [
                {
                  color: item.color,
                  id: item.id,
                  label: item.label,
                  value: point.value,
                },
              ];
        });

  const setHoverFromPointer = (event: PointerEvent<SVGSVGElement>): void => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (rect.width <= 0) {
      if (hoverTimestamp !== null) onHoverTimestamp(null);
      return;
    }
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    const index = Math.round(ratio * (axis.length - 1));
    const nextTimestamp = axis[index] ?? null;
    if (nextTimestamp !== hoverTimestamp) onHoverTimestamp(nextTimestamp);
  };

  const handlePointerDown = (event: PointerEvent<SVGSVGElement>): void => {
    if (event.pointerType === "touch") event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    setHoverFromPointer(event);
  };

  const handlePointerUp = (event: PointerEvent<SVGSVGElement>): void => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  return (
    <div className="relative cursor-crosshair">
      <svg
        aria-label="sparkline"
        role="img"
        viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
        preserveAspectRatio="none"
        className="block h-16 w-full touch-none select-none"
        onPointerDown={handlePointerDown}
        onPointerMove={setHoverFromPointer}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onPointerLeave={(event) => {
          if (event.pointerType !== "touch" && hoverTimestamp !== null) {
            onHoverTimestamp(null);
          }
        }}
      >
        <title>{`${name} — ${series.length} series, ${axis.length} timestamps`}</title>
        {plottedSeries.flatMap((item) =>
          item.paths.map((segment) => (
            <path
              key={`area-${item.id}-${segment.key}`}
              d={segment.areaPath}
              className={COLOR_CLASSES[item.color].fill}
              opacity="0.08"
            />
          )),
        )}
        {plottedSeries.flatMap((item) =>
          item.paths.map((segment) => (
            <path
              key={`line-${item.id}-${segment.key}`}
              d={segment.linePath}
              className={COLOR_CLASSES[item.color].stroke}
              strokeWidth="0.9"
              fill="none"
              vectorEffect="non-scaling-stroke"
            />
          )),
        )}
        {hoverX === null ? null : (
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
            {hoveredValues.map((item) => (
              <circle
                key={item.id}
                cx={hoverX}
                cy={yFor(item.value)}
                r="1.3"
                className={`${COLOR_CLASSES[item.color].fill} stroke-paper`}
                strokeWidth="0.5"
                vectorEffect="non-scaling-stroke"
              />
            ))}
          </g>
        )}
      </svg>
      {hoveredValues.length === 0 ? null : (
        <div
          role="tooltip"
          data-hover-timestamp={hoverTimestamp ?? undefined}
          className="pointer-events-none absolute right-0 top-0 border border-rule-strong bg-paper px-1.5 py-px font-mono text-fs-10 tabular-nums"
        >
          {hoveredValues.map((item) => (
            <div key={item.id} className={COLOR_CLASSES[item.color].text}>
              {hoveredValues.length > 1 ? `${item.label}: ` : ""}
              {formatMetricDisplayValue(item.value, valuePrecision, unit)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

type PathPoint = {
  x: number;
  y: number;
};

type PathSegment = {
  areaPath: string;
  key: string;
  linePath: string;
};

function buildPathSegments(
  points: readonly HistoryPoint[],
  xFor: (index: number) => number,
  yFor: (value: number) => number,
): PathSegment[] {
  const segments: PathSegment[] = [];
  let current: PathPoint[] = [];
  let startIndex = 0;

  const flush = (endIndex: number): void => {
    if (current.length === 0) return;
    const linePath = current
      .map((point, index) => {
        const command = index === 0 ? "M" : "L";
        return `${command} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
      })
      .join(" ");
    const first = current[0];
    const last = current[current.length - 1];
    if (first === undefined || last === undefined) return;
    segments.push({
      key: `${startIndex}-${endIndex}`,
      linePath,
      areaPath: `${linePath} L ${last.x.toFixed(2)} ${VIEWBOX_H} L ${first.x.toFixed(2)} ${VIEWBOX_H} Z`,
    });
    current = [];
  };

  points.forEach((point, index) => {
    if (point.value === null) {
      flush(index - 1);
      return;
    }
    if (current.length === 0) startIndex = index;
    current.push({ x: xFor(index), y: yFor(point.value) });
  });
  flush(points.length - 1);

  return segments;
}
