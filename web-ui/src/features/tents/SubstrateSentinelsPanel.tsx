import { type ReactNode, useMemo, useState } from "react";
import type { hostedComponents } from "@/api-client";
import {
  alignHistoryPoints,
  historyTimestampAxis,
  PLANT_SERIES_COLORS,
} from "@/shared/historySeries";
import { HoverTimestamp } from "@/ui/HoverTimestamp";
import { formatEmptyHistoryLabel } from "@/ui/historyRangeLabels";
import type { SparklineRange } from "@/ui/RangeSwitch";
import { Sparkline, type SparklineSeries } from "@/ui/Sparkline";

type PlantMetricHistoryCollection =
  hostedComponents["schemas"]["PlantMetricHistoryCollectionResponse"];

const SUBSTRATE_HISTORY_METRICS = [
  {
    emptyName: "soil moisture",
    fallbackName: "Soil moisture",
    fallbackUnit: "%",
    metric: "soil_moisture_pct",
  },
  {
    emptyName: "substrate EC",
    fallbackName: "Substrate EC",
    fallbackUnit: "mS/cm",
    metric: "substrate_ec_us_cm",
  },
  {
    emptyName: "substrate pH",
    fallbackName: "Substrate pH",
    fallbackUnit: "pH",
    metric: "substrate_ph",
  },
] as const satisfies readonly {
  emptyName: string;
  fallbackName: string;
  fallbackUnit: string;
  metric: string;
}[];

export function SubstrateSentinelsPanel({
  error,
  history,
  loading,
  range,
}: {
  error: boolean;
  history: PlantMetricHistoryCollection | undefined;
  loading: boolean;
  range: SparklineRange;
}): ReactNode {
  const [hoverState, setHoverState] = useState<{
    range: SparklineRange;
    timestamp: string | null;
  }>({ range, timestamp: null });
  const model = useMemo(() => buildPanelModel(history), [history]);
  const requestedHoverTimestamp =
    hoverState.range === range ? hoverState.timestamp : null;
  const hoverTimestamp =
    requestedHoverTimestamp !== null &&
    model.historyAxis.includes(requestedHoverTimestamp)
      ? requestedHoverTimestamp
      : null;

  return (
    <section aria-label="Substrate sentinels" className="mb-4 flex flex-col">
      <header className="flex min-h-9 items-baseline justify-between gap-3 border border-rule-strong bg-paper-2 px-3.5 py-2">
        <h3 className="font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
          Substrate sentinels
        </h3>
        <HoverTimestamp timestamp={hoverTimestamp} />
      </header>
      {loading ? (
        <PanelStatus label="Loading substrate history…" />
      ) : error ? (
        <PanelStatus error label="Failed to load substrate history." />
      ) : model.streamCount === 0 ? (
        <PanelStatus label="No mapped substrate sentinels for this tent." />
      ) : (
        <div className="grid grid-cols-1 gap-4 border-x border-b border-rule-strong bg-paper p-3 lg:grid-cols-3">
          {model.charts.map((chart) => (
            <Sparkline
              key={chart.metric}
              bucket={model.bucket}
              chrome="card"
              emptyLabel={
                chart.series.length === 0
                  ? `No mapped ${chart.emptyName} stream`
                  : formatEmptyHistoryLabel(range)
              }
              hoverTimestamp={hoverTimestamp}
              name={chart.name}
              onHoverTimestamp={(timestamp) => {
                setHoverState({ range, timestamp });
              }}
              series={chart.series}
              unit={chart.unit}
              valuePrecision={chart.valuePrecision}
              {...chart.yDomain}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function buildPanelModel(history: PlantMetricHistoryCollection | undefined) {
  if (history === undefined) {
    return { bucket: "5m" as const, charts: [], historyAxis: [], streamCount: 0 };
  }

  const orderedPlants = [...history.plants].sort(compareSentinelPlants);
  const substrateStreams = orderedPlants.flatMap((plant) =>
    plant.streams.flatMap((stream) =>
      SUBSTRATE_HISTORY_METRICS.some((item) => item.metric === stream.metric)
        ? [{ plant, stream }]
        : [],
    ),
  );
  const historyAxis = historyTimestampAxis(
    substrateStreams.map(({ stream }) => stream.points),
    history.bucket,
  );
  const plantColors = new Map(
    orderedPlants.map((plant, index) => [
      plant.id,
      PLANT_SERIES_COLORS[index % PLANT_SERIES_COLORS.length] ?? "plant-a",
    ]),
  );
  const charts = SUBSTRATE_HISTORY_METRICS.map((metric) => {
    const mappedStreams = substrateStreams.filter(
      ({ stream }) => stream.metric === metric.metric,
    );
    const firstStream = mappedStreams[0]?.stream;
    const series = mappedStreams.map(({ plant, stream }) => ({
      color: plantColors.get(plant.id) ?? "plant-a",
      id: `${plant.id}:${stream.device_id}:${stream.capability_id}:${stream.metric}`,
      label: sentinelLabel(plant.name, plant.grid_position),
      points: alignHistoryPoints(stream.points, historyAxis),
    })) satisfies readonly SparklineSeries[];
    const yDomain = {
      ...(firstStream?.y_min !== null && firstStream?.y_min !== undefined
        ? { yMin: firstStream.y_min }
        : {}),
      ...(firstStream?.y_max !== null && firstStream?.y_max !== undefined
        ? { yMax: firstStream.y_max }
        : {}),
    };
    return {
      emptyName: metric.emptyName,
      metric: metric.metric,
      name: firstStream?.display_name ?? metric.fallbackName,
      series,
      unit: firstStream?.display_unit ?? metric.fallbackUnit,
      valuePrecision: firstStream?.value_precision ?? 1,
      yDomain,
    };
  });

  return {
    bucket: history.bucket,
    charts,
    historyAxis,
    streamCount: substrateStreams.length,
  };
}

function PanelStatus({
  error = false,
  label,
}: {
  error?: boolean;
  label: string;
}): ReactNode {
  return (
    <div className="border-x border-b border-rule-strong bg-paper-2 p-4">
      <p
        className={
          error
            ? "font-mono text-fs-10 uppercase tracking-caps text-accent-magenta"
            : "font-mono text-fs-10 uppercase tracking-caps text-ink-3"
        }
      >
        {label}
      </p>
    </div>
  );
}

function compareSentinelPlants(
  left: PlantMetricHistoryCollection["plants"][number],
  right: PlantMetricHistoryCollection["plants"][number],
): number {
  return (
    (left.grid_position ?? left.name).localeCompare(
      right.grid_position ?? right.name,
    ) || left.key.localeCompare(right.key)
  );
}

function sentinelLabel(name: string, gridPosition: string | null): string {
  return gridPosition === null ? name : `${name} · ${gridPosition}`;
}
