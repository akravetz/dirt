import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useState } from "react";
import { createHostedApiClient, type hostedComponents } from "@/api-client";
import { HoverTimestamp } from "@/ui/HoverTimestamp";
import { formatEmptyHistoryLabel } from "@/ui/historyRangeLabels";
import { MarkdownDocument } from "@/ui/MarkdownDocument";
import {
  MoistureComparisonChart,
  type MoistureComparisonSeries,
} from "@/ui/MoistureComparisonChart";
import { PlantSticker } from "@/ui/PlantSticker";
import { RangeSwitch, type SparklineRange } from "@/ui/RangeSwitch";

export const Route = createFileRoute("/tents/$tentId/plants/$plantId")({
  component: HostedPlantDetailPage,
});

const hostedApi = createHostedApiClient();
const DASHBOARD_ROUTE = "/" as const;
const PLANT_DETAIL_PATH = "/api/tents/{tent_id}/plants/{plant_id}" as const;
const PLANT_COMPARISON_HISTORY_PATH =
  "/api/tents/{tent_id}/plants/moisture/history" as const;

type PlantMoistureComparison =
  hostedComponents["schemas"]["PlantMoistureComparisonResponse"];

function HostedPlantDetailPage() {
  const { tentId, plantId } = Route.useParams();
  const [range, setRange] = useState<SparklineRange>("24h");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [hoverTimestamp, setHoverTimestamp] = useState<string | null>(null);

  const detailQuery = useQuery({
    queryKey: ["cloud.plants.detail", tentId, plantId],
    queryFn: async () => {
      const { data } = await hostedApi.GET(PLANT_DETAIL_PATH, {
        params: { path: { tent_id: tentId, plant_id: plantId } },
      });
      return hostedData(data, PLANT_DETAIL_PATH);
    },
    retry: false,
  });

  const comparisonQuery = useQuery({
    queryKey: ["cloud.plants.moisture.comparison", tentId, range],
    queryFn: async () => {
      const { data } = await hostedApi.GET(PLANT_COMPARISON_HISTORY_PATH, {
        params: {
          path: { tent_id: tentId },
          query: { range },
        },
      });
      return hostedData(data, PLANT_COMPARISON_HISTORY_PATH);
    },
    retry: false,
  });

  const detail = detailQuery.data ?? null;
  const comparison = comparisonQuery.data ?? null;
  const comparisonSeries =
    comparison === null ? [] : toMoistureComparisonSeries(comparison);
  const selectedComparison = comparison?.plants.find(
    (plant) => plant.plant_id === plantId,
  );
  const unit =
    detail?.latest_moisture?.unit ??
    selectedComparison?.latest_moisture?.unit ??
    selectedComparison?.points[0]?.unit ??
    "%";

  if (detailQuery.isLoading) {
    return (
      <main className="flex-1 overflow-auto p-6">
        <p className="font-mono text-xs uppercase tracking-caps text-ink-3">
          Loading plant detail…
        </p>
      </main>
    );
  }

  if (detailQuery.error || detail === null) {
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
              <PlantSticker color={detail.sticker_color} />
            </div>
            <p className="mt-1 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              {detail.tent_id} · {detail.grow_run_id} · plant {detail.plant_id}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 lg:justify-end">
            <PlantPill tone={detail.is_active ? "ok" : "warn"}>
              {detail.is_active ? "Active" : "Inactive"}
            </PlantPill>
            <PlantPill tone={detail.freshness?.is_current ? "ok" : "warn"}>
              {detail.freshness?.is_current ? "Current" : "Stale"}
            </PlantPill>
            <PlantPill tone={detail.purple ? "purple" : "neutral"}>
              {detail.status}
            </PlantPill>
          </div>
        </header>

        <section className="grid grid-cols-1 gap-px border border-rule-strong bg-rule sm:grid-cols-3">
          <PlantFact
            label="Current Moisture"
            value={
              detail.latest_moisture === null
                ? "No reading"
                : formatMoisture(detail.latest_moisture.value, unit)
            }
          />
          <PlantFact
            label="Target Band"
            value={formatTargetBounds(
              detail.target_bounds.low,
              detail.target_bounds.high,
            )}
          />
          <PlantFact
            label="Freshness"
            value={
              detail.freshness === null
                ? "unknown"
                : formatDuration(detail.freshness.source_age_s)
            }
          />
        </section>

        <section aria-label="Plant moisture comparison" className="flex flex-col">
          <header className="sticky top-0 z-20 flex flex-col gap-2 border-b border-rule bg-paper/95 px-0.5 py-2 backdrop-blur sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-h-7 items-baseline justify-between gap-3">
              <h2 className="font-sans text-fs-11 font-semibold uppercase tracking-cap-wide text-ink-2">
                Moisture Comparison
              </h2>
              <HoverTimestamp
                hoverIndex={hoverIndex}
                points={[]}
                timestamp={hoverTimestamp}
              />
            </div>
            <RangeSwitch value={range} onChange={setRange} />
          </header>
          <div className="border border-rule-strong bg-paper-2">
            <MoistureComparisonChart
              series={comparisonSeries}
              selectedPlantId={plantId}
              unit={unit}
              emptyLabel={
                comparisonQuery.isLoading
                  ? "Loading data"
                  : formatEmptyHistoryLabel(range)
              }
              hoverIndex={hoverIndex}
              onHoverIndex={setHoverIndex}
              onHoverTimestamp={setHoverTimestamp}
            />
          </div>
          {comparisonQuery.error ? (
            <p className="border-x border-b border-rule-strong bg-paper-2 px-3.5 py-2 font-mono text-fs-10 uppercase tracking-caps text-accent-magenta">
              Moisture comparison unavailable
            </p>
          ) : null}
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

function hostedData<T>(data: T | undefined, path: string): T {
  if (data === undefined) {
    throw new Error(`GET ${path} returned no data`);
  }
  return data;
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
  tone: "ok" | "warn" | "purple" | "neutral";
}): ReactNode {
  const toneClass =
    tone === "ok"
      ? "border-status-ok text-status-ok"
      : tone === "warn"
        ? "border-status-warn text-status-warn"
        : tone === "purple"
          ? "border-accent-purple text-accent-purple"
          : "border-rule text-ink-3";
  return (
    <span
      className={`inline-flex border bg-paper-2 px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps ${toneClass}`}
    >
      {children}
    </span>
  );
}

function toMoistureComparisonSeries(
  comparison: PlantMoistureComparison,
): MoistureComparisonSeries[] {
  return comparison.plants.map((plant) => ({
    plantId: plant.plant_id,
    name: plant.name,
    stickerColor: plant.sticker_color,
    latestValue: plant.latest_moisture?.value ?? null,
    points: plant.points.map((point) => ({
      ts: point.bucket_start_at,
      value: point.avg ?? point.max ?? point.min ?? null,
    })),
  }));
}

function formatMoisture(value: number, unit: string | null): string {
  const rounded = Math.round(value * 10) / 10;
  const text = Number.isInteger(rounded) ? `${rounded}` : rounded.toFixed(1);
  if (unit === "raw") return `${text} raw`;
  return unit === null || unit.length === 0 ? text : `${text}${unit}`;
}

function formatTargetBounds(low: number, high: number): string {
  return `${formatPercent(low)}-${formatPercent(high)}`;
}

function formatPercent(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  const text = Number.isInteger(rounded) ? `${rounded}` : rounded.toFixed(1);
  return `${text}%`;
}

function formatDuration(seconds: number): string {
  const safeSeconds = Math.max(0, Math.round(seconds));
  if (safeSeconds < 60) return `${safeSeconds}s ago`;
  const minutes = Math.round(safeSeconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "unknown";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}
