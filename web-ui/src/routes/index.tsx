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
import { HumidifierStrip } from "@/ui/HumidifierStrip";
import { HumidifierTile } from "@/ui/HumidifierTile";
import { PlantDetail } from "@/ui/PlantDetail";
import { PlantsStrip } from "@/ui/PlantsStrip";
import type { PlantCode } from "@/ui/plant-types";
import { RangeSwitch, type SparklineRange } from "@/ui/RangeSwitch";
import { Sparkline } from "@/ui/Sparkline";

export const Route = createFileRoute("/")({
  component: DashboardPage,
});

const api = createDirtApiClient();

type SensorsCurrent = components["schemas"]["SensorsCurrent"];
type MetricEnvelope = components["schemas"]["MetricEnvelope"];

// Single source of truth for the dashboard's five metric tiles. The
// gauges section indexes SensorsCurrent.metrics by `metric`; the
// sparklines section below passes the same `metric` through as
// /api/sensors/history's ?metric= query param (the openapi `SensorMetric`
// enum is a superset — dew_point_f / pressure_hpa are valid history
// metrics but not surfaced on the gauge envelope, so the tighter type
// here is `keyof SensorsCurrent["metrics"]`). `integer` drops the
// decimal on whole-percent and whole-unit metrics (fan_pct,
// reservoir_in both read better as integers).
const METRIC_TILES: ReadonlyArray<{
  metric: keyof SensorsCurrent["metrics"];
  name: string;
  integer?: boolean;
}> = [
  { metric: "temperature_f", name: "Temperature" },
  { metric: "humidity_pct", name: "Humidity", integer: true },
  { metric: "vpd_kpa", name: "VPD" },
  { metric: "fan_pct", name: "Fan", integer: true },
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
  // Selected plant drives the detail drawer. null = drawer closed;
  // a/b/c/d = drawer open for that plant. The per-plant useQuery below
  // is enabled exactly when this is non-null, so flipping the state
  // fires GET /api/plants/{code}.
  const [selectedPlant, setSelectedPlant] = useState<PlantCode | null>(null);

  // Five parallel history queries keyed on [range, metric]. useQueries
  // is the correct idiom for a fixed-shape fan-out: one result slot per
  // metric, all invalidated when `range` changes → the network layer
  // observes five fresh GET /api/sensors/history requests per range
  // switch (one per metric).
  const historyResults = useQueries({
    queries: METRIC_TILES.map(({ metric }) => ({
      queryKey: ["sensors.history", range, metric] as const,
      queryFn: async () => {
        const { data, error } = await api.GET("/api/sensors/history", {
          params: { query: { range, metric } },
        });
        if (error) throw error;
        return data;
      },
    })),
  });

  // /api/humidifier/state: current on/off + last transition. Not keyed
  // on `range` — only the duty-cycle strip below switches with it.
  const humidifierState = useQuery({
    queryKey: ["humidifier.state"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/humidifier/state");
      if (error) throw error;
      return data;
    },
  });

  // /api/humidifier/history — keyed on the same `range` state the
  // sparklines use, so toggling 1h/24h/7d invalidates this query and
  // issues exactly one fresh fetch alongside the per-metric sparkline
  // fetches.
  const humidifierHistory = useQuery({
    queryKey: ["humidifier.history", range] as const,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/humidifier/history", {
        params: { query: { range } },
      });
      if (error) throw error;
      return data;
    },
  });

  // /api/plants — feeds the four A/B/C/D cards rendered under the
  // sparklines. Independent of the range switch; the strip is an
  // always-on snapshot (see frontend.dashboard.plants_strip).
  const plantsQuery = useQuery({
    queryKey: ["plants.list"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/plants");
      if (error) throw error;
      return data;
    },
  });

  // Plant-detail drawer queries — only fetch while a plant is selected
  // so the network activity lines up exactly with "user clicked a
  // card". Closing the drawer (selectedPlant = null) leaves the cache
  // intact; re-opening the same plant serves from cache while also
  // kicking off a background refetch.
  const plantDetailQuery = useQuery({
    queryKey: ["plants.detail", selectedPlant] as const,
    queryFn: async () => {
      if (selectedPlant === null) throw new Error("no plant selected");
      const { data, error } = await api.GET("/api/plants/{code}", {
        params: { path: { code: selectedPlant } },
      });
      if (error) throw error;
      return data;
    },
    enabled: selectedPlant !== null,
  });
  const plantMoistureQuery = useQuery({
    queryKey: ["plants.moisture", selectedPlant, "24h"] as const,
    queryFn: async () => {
      if (selectedPlant === null) throw new Error("no plant selected");
      const { data, error } = await api.GET("/api/plants/{code}/moisture", {
        params: { path: { code: selectedPlant }, query: { range: "24h" } },
      });
      if (error) throw error;
      return data;
    },
    enabled: selectedPlant !== null,
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
        {METRIC_TILES.map(({ metric, name, integer }) => {
          const envelope = data.metrics[metric];
          // Spread `format` conditionally so exactOptionalPropertyTypes
          // sees either the prop set to a function or omitted entirely,
          // never `format: undefined`.
          const formatProp = integer ? { format: formatInteger } : {};
          return (
            <Gauge
              key={metric}
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
      {humidifierState.data ? (
        <section
          aria-label="Humidifier"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          <HumidifierTile
            on={humidifierState.data.on}
            durationS={humidifierState.data.duration_s}
            cycles24h={humidifierState.data.cycles_24h}
          />
        </section>
      ) : null}
      <section aria-label="Environment sparklines" className="flex flex-col gap-3">
        <header className="flex items-center justify-between">
          <h2 className="font-mono text-xs uppercase tracking-caps text-ink-2">
            Sparklines
          </h2>
          <RangeSwitch value={range} onChange={setRange} />
        </header>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {METRIC_TILES.map(({ metric, name }, idx) => {
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
      <HumidifierStrip points={humidifierHistory.data?.points ?? []} />
      {plantsQuery.data ? (
        <PlantsStrip plants={plantsQuery.data.plants} onSelect={setSelectedPlant} />
      ) : null}
      {selectedPlant !== null && plantDetailQuery.data ? (
        <PlantDetail
          payload={plantDetailQuery.data}
          moistureHistory={plantMoistureQuery.data?.points ?? []}
          irrigationEvents24h={plantMoistureQuery.data?.irrigation_events_24h ?? 0}
          onClose={() => {
            setSelectedPlant(null);
          }}
        />
      ) : null}
    </main>
  );
}
