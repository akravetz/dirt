// Dashboard route (/) — five-gauge tile grid + sparklines strip.
//
// Fetches /api/sensors/current via TanStack Query. MSW intercepts the
// request in dev + e2e tests (see web-ui/src/mocks/handlers.ts); in
// production the same call hits the real backend on :8001. No
// re-derivation of band_status happens here — the envelope's `status`
// field is the authoritative value the backend stamps onto each
// reading (see apps/shared/src/dirt_shared/services/grow_state.py).
//
// Under the gauges, a 1h/24h/7d range switch + five sparklines render
// bucketed history from /api/sensors/history (one fetch per metric per
// range change, keyed on [metric, range] so changing the range
// invalidates all five). A shared `hoverIndex` state moves a crosshair
// across every sparkline in lockstep.
//
// useQuery over a route loader keeps the route component purely
// declarative and lets React Query manage retries + background
// refetches uniformly across the SPA. See
// docs/references/tanstack-router-v1/loaders.md for the loader
// alternative if a future change needs SSR-style prefetch.
import { useQueries, useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { type components, createDirtApiClient } from "@/api-client";
import { Gauge } from "@/ui/Gauge";
import { RangeSwitch, type SparklineRange } from "@/ui/RangeSwitch";
import { Sparkline } from "@/ui/Sparkline";

export const Route = createFileRoute("/")({
  component: DashboardPage,
});

const api = createDirtApiClient();

type SensorsCurrent = components["schemas"]["SensorsCurrent"];
type MetricEnvelope = components["schemas"]["MetricEnvelope"];
type SensorMetric = components["schemas"]["SensorMetric"];
type SensorsHistoryResponse = components["schemas"]["SensorsHistoryResponse"];

// Display order + labels for the five gauges. `key` picks the
// envelope out of SensorsCurrent.metrics; `name` is the visible
// heading + aria-label the e2e spec matches. `integer` drops the
// decimal on whole-percent and whole-unit metrics (fan_pct,
// reservoir_in both read better as integers).
const GAUGE_TILES: ReadonlyArray<{
  key: keyof SensorsCurrent["metrics"];
  name: string;
  integer?: boolean;
}> = [
  { key: "temperature_f", name: "Temperature" },
  { key: "humidity_pct", name: "Humidity", integer: true },
  { key: "vpd_kpa", name: "VPD" },
  { key: "fan_pct", name: "Fan", integer: true },
  { key: "reservoir_in", name: "Reservoir" },
] as const;

// Sparklines reuse the gauge ordering + display names for a 1:1 visual
// correspondence between a metric's gauge and its trace beneath. The
// `metric` field is the contract enum (SensorMetric) the /api/sensors/
// history endpoint accepts on its `?metric=` query param.
const SPARKLINE_TILES: ReadonlyArray<{
  metric: SensorMetric;
  name: string;
}> = [
  { metric: "temperature_f", name: "Temperature" },
  { metric: "humidity_pct", name: "Humidity" },
  { metric: "vpd_kpa", name: "VPD" },
  { metric: "fan_pct", name: "Fan" },
  { metric: "reservoir_in", name: "Reservoir" },
] as const;

function toBand(target: MetricEnvelope["target"]): readonly [number, number] | null {
  if (target === null) return null;
  // Contract defines TargetBand as `number[]` (tuple), but openapi-
  // typescript widens it. Guard the length explicitly rather than
  // asserting `as`.
  if (target.length < 2) return null;
  return [target[0] as number, target[1] as number] as const;
}

function formatInteger(value: number): string {
  return `${Math.round(value)}`;
}

// Fetch one metric's bucketed history. Query key includes both range
// and metric so switching the range invalidates all five queries
// simultaneously → the network layer observes five fresh GET
// /api/sensors/history requests per range switch (one per metric).
function buildHistoryQuery(
  metric: SensorMetric,
  range: SparklineRange,
): {
  queryKey: readonly [string, SparklineRange, SensorMetric];
  queryFn: () => Promise<SensorsHistoryResponse>;
} {
  return {
    queryKey: ["sensors.history", range, metric] as const,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/sensors/history", {
        params: { query: { range, metric } },
      });
      if (error) throw error;
      return data;
    },
  };
}

function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["sensors.current"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/sensors/current");
      if (error) throw error;
      return data;
    },
  });

  const [range, setRange] = useState<SparklineRange>("24h");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  // Five parallel history queries keyed on [range, metric]. useQueries
  // is the correct idiom for a fixed-shape fan-out: one result slot per
  // metric, all invalidated when `range` changes.
  const historyResults = useQueries({
    queries: SPARKLINE_TILES.map(({ metric }) => buildHistoryQuery(metric, range)),
  });

  if (isLoading) {
    return (
      <main className="p-6">
        <p className="font-mono text-xs uppercase tracking-caps text-ink-3">
          Loading sensors…
        </p>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="p-6">
        <p className="font-mono text-xs uppercase tracking-caps text-accent-magenta">
          Failed to load sensors
        </p>
      </main>
    );
  }

  return (
    <main className="flex flex-1 flex-col gap-6 p-6">
      <section
        aria-label="Environment gauges"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5"
      >
        {GAUGE_TILES.map(({ key, name, integer }) => {
          const envelope = data.metrics[key];
          // Spread `format` conditionally so exactOptionalPropertyTypes
          // sees either the prop set to a function or omitted entirely,
          // never `format: undefined`.
          const formatProp = integer ? { format: formatInteger } : {};
          return (
            <Gauge
              key={key}
              name={name}
              value={envelope.value}
              unit={envelope.unit}
              band={toBand(envelope.target)}
              status={envelope.status}
              {...formatProp}
            />
          );
        })}
      </section>
      <section aria-label="Environment sparklines" className="flex flex-col gap-3">
        <header className="flex items-center justify-between">
          <h2 className="font-mono text-xs uppercase tracking-caps text-ink-2">
            Sparklines
          </h2>
          <RangeSwitch value={range} onChange={setRange} />
        </header>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {SPARKLINE_TILES.map(({ metric, name }, idx) => {
            const result = historyResults[idx];
            const points = result?.data?.points ?? [];
            const unit = result?.data?.unit ?? "";
            return (
              <Sparkline
                key={metric}
                name={name}
                points={points}
                unit={unit}
                hoverIndex={hoverIndex}
                onHoverIndex={setHoverIndex}
              />
            );
          })}
        </div>
      </section>
    </main>
  );
}
