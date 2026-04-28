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
import { HoverTimestamp } from "@/ui/HoverTimestamp";
import { PlantDetail } from "@/ui/PlantDetail";
import { PlantsStrip } from "@/ui/PlantsStrip";
import type { PlantCode } from "@/ui/plant-types";
import { RangeSwitch, type SparklineRange } from "@/ui/RangeSwitch";
import { Sparkline } from "@/ui/Sparkline";
import { SystemTable } from "@/ui/SystemTable";

export const Route = createFileRoute("/")({
  component: DashboardPage,
});

const api = createDirtApiClient();

type SensorsCurrent = components["schemas"]["SensorsCurrent"];
type MetricEnvelope = components["schemas"]["MetricEnvelope"];
type MetricMeta = components["schemas"]["SensorMetricMetadata"];
type SparklineAccent = "temp" | "humidity" | "vpd" | "moisture" | "neutral";

// Whitelist the accent strings the FE knows how to render. Anything else
// from the registry falls back to "neutral" so a future BE addition
// can't break the SPA visually.
const KNOWN_ACCENTS: ReadonlySet<SparklineAccent> = new Set([
  "temp",
  "humidity",
  "vpd",
  "moisture",
  "neutral",
]);

function asAccent(raw: string): SparklineAccent {
  return KNOWN_ACCENTS.has(raw as SparklineAccent)
    ? (raw as SparklineAccent)
    : "neutral";
}

// Metrics that display as integers (no decimal). Driven by the unit
// being unitless `%` or `in`; keeps the formatter rule local to the FE
// without dragging a bool through the contract.
function isIntegerMetric(m: MetricMeta): boolean {
  return m.unit === "%" || m.unit === "in";
}

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

function freshnessLabel(data: SensorsCurrent): {
  label: string;
  dotClass: string;
} {
  if (data.stale) {
    return { label: "stale", dotClass: "text-status-warn" };
  }
  return { label: "live", dotClass: "text-status-ok" };
}

function DashboardPage() {
  // Per-metric display metadata — name, unit, accent, y-axis bounds —
  // driven by the BE registry at /api/sensors/metadata. Read once at
  // boot. `staleTime: Infinity` because the registry only changes via
  // a deploy, not at runtime.
  const metaQuery = useQuery({
    queryKey: ["sensors.metadata"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/sensors/metadata");
      if (error) throw error;
      return data;
    },
    staleTime: Number.POSITIVE_INFINITY,
  });
  const metaList = metaQuery.data?.metrics ?? [];

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
  const [plantMoistureRange, setPlantMoistureRange] = useState<SparklineRange>("24h");

  // Parallel history queries — one per dashboard metric. `useQueries`
  // is the right idiom for a metadata-driven fan-out: one result slot
  // per metric, all invalidated when `range` changes → one fresh GET
  // /api/sensors/history per metric per range switch. `enabled` defers
  // the fan-out until metadata loads so we don't fire requests against
  // an empty list and then re-fire them once metadata arrives.
  const historyResults = useQueries({
    queries: metaList.map((m) => ({
      queryKey: ["sensors.history", range, m.metric] as const,
      queryFn: async () => {
        const { data, error } = await api.GET("/api/sensors/history", {
          params: { query: { range, metric: m.metric } },
        });
        if (error) throw error;
        return data;
      },
      enabled: metaQuery.isSuccess,
    })),
  });

  // /api/grow/current — reused from the root loader cache; the Plants
  // section header renders "Plants · Day N" from `day_number`.
  const growQuery = useQuery({
    queryKey: ["grow.current"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/grow/current");
      if (error) throw error;
      return data;
    },
  });
  const growContext = growQuery.data ? { dayNumber: growQuery.data.day_number } : null;

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

  // /api/system/devices — one row per device for the dashboard system
  // table rendered below the plants strip. Independent of the range
  // switch; the table is an always-on snapshot (see
  // frontend.dashboard.system_table).
  const systemDevicesQuery = useQuery({
    queryKey: ["system.devices"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/system/devices");
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
    queryKey: ["plants.moisture", selectedPlant, plantMoistureRange] as const,
    queryFn: async () => {
      if (selectedPlant === null) throw new Error("no plant selected");
      const { data, error } = await api.GET("/api/plants/{code}/moisture", {
        params: {
          path: { code: selectedPlant },
          query: { range: plantMoistureRange },
        },
      });
      if (error) throw error;
      return data;
    },
    enabled: selectedPlant !== null,
  });

  if (isLoading || metaQuery.isLoading) {
    return (
      <main className="flex-1 overflow-auto p-6">
        <p className="font-mono text-xs uppercase tracking-caps text-ink-3">
          Loading sensors…
        </p>
      </main>
    );
  }

  if (error || !data || metaQuery.error || !metaQuery.data) {
    return (
      <main className="flex-1 overflow-auto p-6">
        <p className="font-mono text-xs uppercase tracking-caps text-accent-magenta">
          Failed to load sensors
        </p>
      </main>
    );
  }

  const freshness = freshnessLabel(data);

  return (
    <main className="flex-1 overflow-auto">
      <div className="mx-auto flex max-w-350 flex-col gap-6 px-8 pb-16 pt-7">
        <div className="flex items-center justify-end gap-4 border-b border-rule-strong pb-3">
          <span className="inline-flex items-center gap-1.5 font-mono text-fs-11 text-ink-3">
            <span aria-hidden="true" className={freshness.dotClass}>
              ◉
            </span>
            {freshness.label}
          </span>
          <RangeSwitch value={range} onChange={setRange} />
        </div>
        <div className="grid grid-cols-1 gap-px border border-rule-strong bg-rule sm:grid-cols-2 lg:grid-cols-6">
          <section aria-label="Environment gauges" className="contents">
            {metaList.map((m) => {
              const envelope =
                data.metrics[m.metric as keyof SensorsCurrent["metrics"]];
              if (envelope === undefined) return null;
              const formatProp = isIntegerMetric(m) ? { format: formatInteger } : {};
              return (
                <Gauge
                  key={m.metric}
                  name={m.display_name}
                  value={envelope.value}
                  unit={envelope.unit}
                  band={toBand(envelope.target)}
                  status={envelope.status}
                  accent={asAccent(m.accent)}
                  {...formatProp}
                />
              );
            })}
          </section>
        </div>
        <section aria-label="Environment history" className="flex flex-col">
          <header className="flex items-baseline justify-between border-b border-rule px-0.5 py-2">
            <h2 className="font-sans text-fs-11 font-semibold uppercase tracking-cap-wide text-ink-2">
              History
            </h2>
            <HoverTimestamp
              hoverIndex={hoverIndex}
              points={historyResults.find((r) => r.data)?.data?.points ?? []}
            />
          </header>
          <div className="grid grid-cols-1 border border-rule-strong bg-paper-2 sm:grid-cols-2 lg:grid-cols-3">
            {metaList.map((m, idx) => {
              const result = historyResults[idx];
              const points = result?.data?.points ?? [];
              const unit = result?.data?.unit ?? m.unit;
              const yProps = {
                ...(m.y_min !== null && m.y_min !== undefined ? { yMin: m.y_min } : {}),
                ...(m.y_max !== null && m.y_max !== undefined ? { yMax: m.y_max } : {}),
              };
              return (
                <Sparkline
                  key={m.metric}
                  name={m.display_name}
                  points={points}
                  unit={unit}
                  accent={asAccent(m.accent)}
                  hoverIndex={hoverIndex}
                  onHoverIndex={setHoverIndex}
                  {...yProps}
                />
              );
            })}
          </div>
        </section>
        {plantsQuery.data ? (
          <PlantsStrip
            plants={plantsQuery.data.plants}
            dayNumber={growContext?.dayNumber ?? null}
            onSelect={setSelectedPlant}
          />
        ) : null}
        {systemDevicesQuery.data ? (
          <SystemTable devices={systemDevicesQuery.data.devices} />
        ) : null}
      </div>
      {selectedPlant !== null && plantDetailQuery.data ? (
        <PlantDetail
          payload={plantDetailQuery.data}
          moistureHistory={plantMoistureQuery.data?.points ?? []}
          moistureRange={plantMoistureRange}
          onMoistureRangeChange={setPlantMoistureRange}
          onClose={() => {
            setSelectedPlant(null);
          }}
        />
      ) : null}
    </main>
  );
}
