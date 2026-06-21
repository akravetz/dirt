import { queryOptions, useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { Suspense, useState } from "react";
import { createHostedApiClient, type hostedComponents } from "@/api-client";
import { formatMetricValue } from "@/shared/metricFormat";
import { HoverTimestamp } from "@/ui/HoverTimestamp";
import { formatEmptyHistoryLabel } from "@/ui/historyRangeLabels";
import { MarkdownDocument } from "@/ui/MarkdownDocument";
import { RangeSwitch, type SparklineRange } from "@/ui/RangeSwitch";
import { Sparkline } from "@/ui/Sparkline";

export const Route = createFileRoute("/tents/$sourceTentId/plants/$plantId")({
  component: HostedPlantDetailRoute,
  errorComponent: PlantDetailUnavailableScreen,
});

const hostedApi = createHostedApiClient();
const DASHBOARD_ROUTE = "/" as const;
const PLANT_DETAIL_PATH = "/api/tents/{source_tent_id}/plants/{plant_id}" as const;
const PLANT_METRIC_HISTORY_PATH =
  "/api/tents/{source_tent_id}/plants/{plant_id}/metrics/history" as const;

type SparklineAccent =
  | "temp"
  | "humidity"
  | "vpd"
  | "moisture"
  | "reservoir"
  | "neutral";
type HistoryPoint = {
  ts: string;
  value: number | null;
};
type PlantMetricStream = hostedComponents["schemas"]["PlantMetricStreamResponse"];
type PlantMetricHistoryStream =
  hostedComponents["schemas"]["PlantMetricHistoryStreamResponse"];
type PlantDetail = hostedComponents["schemas"]["PlantDetailResponse"];
type PlantEvent = hostedComponents["schemas"]["PlantEventResponse"];
type PlantNote = hostedComponents["schemas"]["PlantNoteResponse"];

const KNOWN_ACCENTS: ReadonlySet<SparklineAccent> = new Set([
  "temp",
  "humidity",
  "vpd",
  "moisture",
  "reservoir",
  "neutral",
]);

function HostedPlantDetailRoute() {
  return (
    <Suspense fallback={<PlantDetailLoadingScreen />}>
      <HostedPlantDetailPage />
    </Suspense>
  );
}

function asAccent(raw: string): SparklineAccent {
  return KNOWN_ACCENTS.has(raw as SparklineAccent)
    ? (raw as SparklineAccent)
    : "neutral";
}

function plantDetailOptions(sourceTentId: string, plantId: string) {
  return queryOptions({
    queryKey: ["cloud.plants.detail", sourceTentId, plantId],
    queryFn: async () => {
      const { data } = await hostedApi.GET(PLANT_DETAIL_PATH, {
        params: { path: { source_tent_id: Number(sourceTentId), plant_id: plantId } },
      });
      return hostedData(data, PLANT_DETAIL_PATH);
    },
    retry: false,
  });
}

function HostedPlantDetailPage() {
  const { sourceTentId, plantId } = Route.useParams();
  const [range, setRange] = useState<SparklineRange>("24h");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [hoverTimestamp, setHoverTimestamp] = useState<string | null>(null);

  const { data: detail } = useSuspenseQuery(plantDetailOptions(sourceTentId, plantId));
  const historyQuery = useQuery({
    queryKey: ["cloud.plants.metrics.history", sourceTentId, plantId, range],
    queryFn: async () => {
      const { data } = await hostedApi.GET(PLANT_METRIC_HISTORY_PATH, {
        params: {
          path: { source_tent_id: Number(sourceTentId), plant_id: plantId },
          query: { range },
        },
      });
      return hostedData(data, PLANT_METRIC_HISTORY_PATH);
    },
    enabled: detail.telemetry.length > 0,
    retry: false,
  });

  const history = historyQuery.data ?? null;
  const historyAxis = buildHistoryAxis(history?.streams ?? []);
  const historyByStream = new Map(
    history?.streams.map((stream) => [metricStreamKey(stream), stream]) ?? [],
  );

  return (
    <main className="flex-1 overflow-auto">
      <div className="mx-auto flex max-w-350 flex-col gap-5 px-5 pb-14 pt-5 sm:px-8 sm:pb-16 sm:pt-7">
        <header className="grid gap-4 border-b border-rule-strong pb-4 lg:grid-cols-[1fr_auto] lg:items-end">
          <div className="min-w-0">
            <Link
              to={DASHBOARD_ROUTE}
              className="mb-3 inline-flex border border-rule px-3 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3 hover:border-rule-strong hover:text-ink"
            >
              Dashboard
            </Link>
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <h1 className="min-w-0 break-words font-sans text-fs-24 font-semibold tracking-tight text-ink">
                {detail.name}
              </h1>
            </div>
            <p className="mt-1 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              {detail.key} · source #{detail.id} · {formatCurrentLocation(detail)}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 lg:justify-end">
            <PlantPill tone={detail.is_active ? "ok" : "warn"}>
              {detail.is_active ? "Active" : "Inactive"}
            </PlantPill>
            <PlantPill tone={detail.telemetry_stream_count > 0 ? "ok" : "neutral"}>
              {formatTelemetryStreamCount(detail.telemetry_stream_count)}
            </PlantPill>
            <PlantPill tone="neutral">{formatLineIdentity(detail)}</PlantPill>
          </div>
        </header>

        <section className="grid grid-cols-1 gap-px border border-rule-strong bg-rule sm:grid-cols-2 lg:grid-cols-4">
          <PlantFact label="Line" value={formatLineIdentity(detail)} />
          <PlantFact label="Current Location" value={formatCurrentLocation(detail)} />
          <PlantFact
            label="Germinated"
            value={formatNullableTimestamp(detail.germinated_at)}
          />
          <PlantFact
            label="Flower Started"
            value={formatNullableTimestamp(detail.flower_started_at)}
          />
          <PlantFact
            label="Veg Started"
            value={formatNullableTimestamp(detail.veg_started_at)}
          />
          <PlantFact label="Taken" value={formatNullableTimestamp(detail.taken_at)} />
          <PlantFact label="Rooted" value={formatNullableTimestamp(detail.rooted_at)} />
          <PlantFact
            label="Selected"
            value={formatNullableTimestamp(detail.selected_for_breeding_at)}
          />
          <PlantFact
            label="Telemetry"
            value={formatTelemetryStreamCount(detail.telemetry_stream_count)}
          />
          <PlantFact
            label="Wiki"
            value={detail.wiki_content === null ? "No content" : "Projected"}
          />
        </section>

        <section aria-label="Telemetry" className="flex flex-col">
          <header className="sticky top-0 z-20 flex flex-col gap-2 border-b border-rule bg-paper/95 px-0.5 py-2 backdrop-blur sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-h-7 items-baseline justify-between gap-3">
              <h2 className="font-sans text-fs-11 font-semibold uppercase tracking-cap-wide text-ink-2">
                Telemetry
              </h2>
              <HoverTimestamp
                hoverIndex={hoverIndex}
                points={historyAxis.map((ts) => ({ ts }))}
                timestamp={hoverTimestamp}
              />
            </div>
            {detail.telemetry.length === 0 ? null : (
              <RangeSwitch value={range} onChange={setRange} />
            )}
          </header>
          {detail.telemetry.length === 0 ? (
            <EmptyTelemetryState />
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {detail.telemetry.map((metric) => {
                const streamHistory = historyByStream.get(metricStreamKey(metric));
                const points =
                  streamHistory === undefined
                    ? []
                    : toSparklinePoints(streamHistory, historyAxis);
                const yProps = {
                  ...(metric.y_min !== null && metric.y_min !== undefined
                    ? { yMin: metric.y_min }
                    : {}),
                  ...(metric.y_max !== null && metric.y_max !== undefined
                    ? { yMax: metric.y_max }
                    : {}),
                };
                return (
                  <MetricTelemetryCard
                    key={metricStreamKey(metric)}
                    metric={metric}
                    points={points}
                    emptyLabel={
                      historyQuery.isLoading
                        ? "Loading data"
                        : formatEmptyHistoryLabel(range)
                    }
                    hoverIndex={hoverIndex}
                    onHoverIndex={setHoverIndex}
                    onHoverTimestamp={setHoverTimestamp}
                    {...yProps}
                  />
                );
              })}
            </div>
          )}
          {historyQuery.error && detail.telemetry.length > 0 ? (
            <p className="border-x border-b border-rule-strong bg-paper-2 px-3.5 py-2 font-mono text-fs-10 uppercase tracking-caps text-accent-magenta">
              Telemetry history unavailable
            </p>
          ) : null}
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <PlantNotesPanel notes={detail.notes} />
          <PlantEventsPanel events={detail.events} />
        </section>

        {detail.wiki_content === null ? (
          <section className="border border-rule-strong bg-paper-2 p-4">
            <h2 className="font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
              Wiki
            </h2>
            <p className="mt-3 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              No projected wiki content for this plant.
            </p>
          </section>
        ) : (
          <section className="border border-rule-strong bg-paper-2 p-4">
            <header className="mb-4 flex flex-wrap items-baseline justify-between gap-2 border-b border-rule pb-3">
              <h2 className="font-sans text-fs-16 font-semibold text-ink">
                {detail.wiki_content.title}
              </h2>
              <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                {formatTimestamp(detail.wiki_content.source_updated_at)}
              </span>
            </header>
            <MarkdownDocument bodyMarkdown={detail.wiki_content.body_markdown} />
          </section>
        )}
      </div>
    </main>
  );
}

function PlantDetailLoadingScreen(): ReactNode {
  return (
    <main className="flex-1 overflow-auto p-6">
      <p className="font-mono text-xs uppercase tracking-caps text-ink-3">
        Loading plant detail…
      </p>
    </main>
  );
}

function PlantDetailUnavailableScreen(): ReactNode {
  return (
    <main className="flex-1 overflow-auto">
      <div className="mx-auto flex max-w-320 flex-col gap-4 px-5 py-6 sm:px-8">
        <Link
          to={DASHBOARD_ROUTE}
          className="w-fit border border-rule px-3 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3 hover:border-rule-strong hover:text-ink"
        >
          Dashboard
        </Link>
        <section className="border border-rule-strong bg-paper-2 p-5">
          <p className="font-mono text-fs-10 uppercase tracking-caps text-accent-magenta">
            Plant detail unavailable
          </p>
        </section>
      </div>
    </main>
  );
}

function MetricTelemetryCard({
  emptyLabel,
  hoverIndex,
  metric,
  onHoverIndex,
  onHoverTimestamp,
  points,
  yMax,
  yMin,
}: {
  emptyLabel: string;
  hoverIndex: number | null;
  metric: PlantMetricStream;
  onHoverIndex: (index: number | null) => void;
  onHoverTimestamp: (timestamp: string | null) => void;
  points: readonly HistoryPoint[];
  yMax?: number;
  yMin?: number;
}): ReactNode {
  const latest = metric.latest_reading;
  const sparklineYProps = {
    ...(yMin !== undefined ? { yMin } : {}),
    ...(yMax !== undefined ? { yMax } : {}),
  };
  return (
    <Sparkline
      chrome="card"
      name={metric.display_name}
      points={metric.history_enabled ? points : []}
      unit={metric.display_unit}
      accent={asAccent(metric.accent)}
      valuePrecision={metric.value_precision}
      emptyLabel={metric.history_enabled ? emptyLabel : "History not enabled"}
      hoverIndex={hoverIndex}
      onHoverIndex={onHoverIndex}
      onHoverPoint={(point) => {
        onHoverTimestamp(point?.ts ?? null);
      }}
      summary={
        <div className="flex flex-col gap-2">
          <div className="flex min-w-0 items-center justify-between gap-3 border-b border-rule pb-2">
            <p className="min-w-0 truncate font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              {metric.device_id} · {metric.capability_id}
            </p>
            <span className="shrink-0 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              {metric.history_enabled ? "History" : "Current"}
            </span>
          </div>
          <div className="grid grid-cols-1 gap-px bg-rule sm:grid-cols-2">
            <MetricFact
              label="Latest"
              value={
                latest === null
                  ? "No reading"
                  : formatReading(
                      latest.value,
                      metric.display_unit,
                      metric.value_precision,
                    )
              }
            />
            <MetricFact
              label="Received"
              value={latest === null ? "Never" : formatTimestamp(latest.received_at)}
            />
          </div>
        </div>
      }
      {...sparklineYProps}
    />
  );
}

function EmptyTelemetryState(): ReactNode {
  return (
    <section className="border border-rule-strong bg-paper-2 px-4 py-5">
      <div className="max-w-160">
        <h3 className="font-sans text-fs-13 font-semibold text-ink">No telemetry</h3>
        <p className="mt-2 text-fs-12 leading-relaxed text-ink-2">
          This plant has no active mapped telemetry streams. Identity, location, and
          projected wiki content are still available.
        </p>
      </div>
    </section>
  );
}

function PlantNotesPanel({ notes }: { notes: readonly PlantNote[] }): ReactNode {
  return (
    <section className="border border-rule-strong bg-paper-2 p-4">
      <header className="mb-3 flex items-baseline justify-between gap-3 border-b border-rule pb-2">
        <h2 className="font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
          Notes
        </h2>
        <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          {notes.length}
        </span>
      </header>
      {notes.length === 0 ? (
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          No projected notes.
        </p>
      ) : (
        <ol className="flex flex-col gap-3">
          {notes.map((note) => (
            <li key={note.id} className="border-b border-rule pb-3 last:border-b-0">
              <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                {formatTimestamp(note.observed_at)}
                {note.created_by === null ? "" : ` · ${note.created_by}`}
              </p>
              <p className="mt-1 text-fs-12 leading-relaxed text-ink">{note.body}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function PlantEventsPanel({ events }: { events: readonly PlantEvent[] }): ReactNode {
  return (
    <section className="border border-rule-strong bg-paper-2 p-4">
      <header className="mb-3 flex items-baseline justify-between gap-3 border-b border-rule pb-2">
        <h2 className="font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
          Events
        </h2>
        <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          {events.length}
        </span>
      </header>
      {events.length === 0 ? (
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          No projected events.
        </p>
      ) : (
        <ol className="flex flex-col gap-3">
          {events.map((event) => (
            <li key={event.id} className="border-b border-rule pb-3 last:border-b-0">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                  {formatEventKinds(event.kinds)}
                </p>
                <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                  {formatTimestamp(event.occurred_at)}
                </p>
              </div>
              {event.reason === null ? null : (
                <p className="mt-1 text-fs-12 leading-relaxed text-ink">
                  {event.reason}
                </p>
              )}
              {event.notes === null ? null : (
                <p className="mt-1 text-fs-12 leading-relaxed text-ink-2">
                  {event.notes}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function hostedData<T>(data: T | undefined, path: string): T {
  if (data === undefined) {
    throw new Error(`GET ${path} returned no data`);
  }
  return data;
}

function MetricFact({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <div className="flex min-w-0 flex-col gap-1 bg-paper px-3.5 py-3">
      <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
        {label}
      </span>
      <span className="truncate font-mono text-fs-12 tabular-nums text-ink">
        {value}
      </span>
    </div>
  );
}

function PlantFact({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <div className="flex min-w-0 flex-col gap-1 bg-paper-2 p-3 sm:p-4">
      <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
        {label}
      </span>
      <span className="truncate font-sans text-fs-13 text-ink">{value}</span>
    </div>
  );
}

function PlantPill({
  children,
  tone,
}: {
  children: ReactNode;
  tone: "ok" | "warn" | "neutral";
}): ReactNode {
  const toneClass =
    tone === "ok"
      ? "border-status-ok text-status-ok"
      : tone === "warn"
        ? "border-status-warn text-status-warn"
        : "border-rule text-ink-3";
  return (
    <span
      className={`inline-flex border bg-paper-2 px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps ${toneClass}`}
    >
      {children}
    </span>
  );
}

function formatTelemetryStreamCount(count: number): string {
  if (count === 0) return "No telemetry";
  return `${count} stream${count === 1 ? "" : "s"}`;
}

function formatReading(value: number, unit: string | null, precision: number): string {
  const formatted = formatMetricValue(value, precision);
  if (unit === "raw") return `${formatted} raw`;
  return unit === null || unit.length === 0 ? formatted : `${formatted}${unit}`;
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "unknown";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function formatNullableTimestamp(value: string | null): string {
  return value === null ? "Not set" : formatTimestamp(value);
}

function formatCurrentLocation(detail: PlantDetail): string {
  return `${detail.current_location.current_tent_name} · ${detail.current_location.grid_position}`;
}

function formatLineIdentity(detail: PlantDetail): string {
  if (detail.line === null) return `line #${detail.line_source_id}`;
  const project = [detail.line.project_code, detail.line.generation_label]
    .filter((part) => part !== null && part.length > 0)
    .join(" ");
  const prefix = project.length > 0 ? `${project} · ` : "";
  return `${prefix}${detail.line.strain} · ${detail.line.cultivar}`;
}

function formatEventKinds(kinds: readonly string[]): string {
  if (kinds.length === 0) return "event";
  return kinds.join(", ");
}

function metricStreamKey(stream: {
  capability_id: string;
  device_id: string;
  metric: string;
}): string {
  return `${stream.device_id}:${stream.capability_id}:${stream.metric}`;
}

function buildHistoryAxis(streams: readonly PlantMetricHistoryStream[]): string[] {
  const timestamps = new Set<string>();
  for (const stream of streams) {
    for (const point of stream.points) {
      timestamps.add(point.bucket_start_at);
    }
  }
  return [...timestamps].sort(compareIsoTimestamps);
}

function compareIsoTimestamps(a: string, b: string): number {
  return new Date(a).getTime() - new Date(b).getTime();
}

function toSparklinePoints(
  history: PlantMetricHistoryStream,
  axis: readonly string[],
): HistoryPoint[] {
  const valuesByTimestamp = new Map(
    history.points.map((point) => [
      point.bucket_start_at,
      point.avg ?? point.max ?? point.min ?? null,
    ]),
  );
  return axis.map((ts) => ({
    ts,
    value: valuesByTimestamp.get(ts) ?? null,
  }));
}
