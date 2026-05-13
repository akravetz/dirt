// Dashboard route (/) — five-gauge tile grid + sparklines strip.
//
// Fetches /api/sensors/current via TanStack Query. No re-derivation of
// band_status happens here — the envelope's `status` field is the
// authoritative value the backend stamps onto each reading (see
// apps/shared/src/dirt_shared/services/grow_state.py).
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
import type { ChangeEvent, ReactNode } from "react";
import { useState } from "react";
import {
  type components,
  createDirtApiClient,
  createHostedApiClient,
  type hostedComponents,
  isHostedApiMode,
} from "@/api-client";
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
const hostedApi = createHostedApiClient();

type SensorsCurrent = components["schemas"]["SensorsCurrent"];
type MetricEnvelope = components["schemas"]["MetricEnvelope"];
type MetricMeta = components["schemas"]["SensorMetricMetadata"];
type SparklineAccent = "temp" | "humidity" | "vpd" | "moisture" | "neutral";
type MetricStatus = MetricEnvelope["status"];
type LocalLightSchedule = components["schemas"]["LightSchedule"];
type HostedAsset = hostedComponents["schemas"]["AssetResponse"];
type HostedDevice = hostedComponents["schemas"]["DeviceResponse"];
type HostedLightSchedule = hostedComponents["schemas"]["LightScheduleResponse"];
type HostedMetric = hostedComponents["schemas"]["CurrentMetricResponse"];
type HostedMetricHistory = hostedComponents["schemas"]["MetricHistoryResponse"];
type HostedSyncStatus = hostedComponents["schemas"]["SyncStatusResponse"];
type DashboardLightSchedule = LocalLightSchedule | HostedLightSchedule;
type MetricFreshness = "live" | "stale";
type MetricCardModel = {
  accent: SparklineAccent;
  format?: (value: number) => string;
  key: string;
  name: string;
  status: MetricStatus;
  unit: string;
  value: number;
};
type MetricSourceModel = {
  key: string;
  label: string;
  value: string;
};
type AssetPanelModel =
  | { state: "unavailable" }
  | { state: "empty" }
  | {
      state: "ready";
      capturedValue: string;
      imageUrl: string;
    };
type DeviceRowModel = {
  id: string;
  kindLabel: string;
  lastSeenLabel: string;
  name: string;
};

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

function hostedData<T>(data: T | undefined, path: string): T {
  if (data === undefined) {
    throw new Error(`GET ${path} returned no data`);
  }
  return data;
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

const HOSTED_METRIC_META: readonly MetricMeta[] = [
  {
    metric: "temperature_f",
    display_name: "Temperature",
    unit: "°F",
    accent: "temp",
    y_min: 60,
    y_max: 90,
    has_target_band: false,
  },
  {
    metric: "humidity_pct",
    display_name: "Humidity",
    unit: "%",
    accent: "humidity",
    y_min: 20,
    y_max: 90,
    has_target_band: false,
  },
  {
    metric: "vpd_kpa",
    display_name: "VPD",
    unit: "kPa",
    accent: "vpd",
    y_min: 0,
    y_max: 2,
    has_target_band: false,
  },
  {
    metric: "fan_pct",
    display_name: "Fan",
    unit: "%",
    accent: "neutral",
    y_min: 0,
    y_max: 100,
    has_target_band: false,
  },
  {
    metric: "humidifier_intensity_pct",
    display_name: "Humidifier",
    unit: "%",
    accent: "humidity",
    y_min: 0,
    y_max: 100,
    has_target_band: false,
  },
  {
    metric: "reservoir_in",
    display_name: "Reservoir",
    unit: "in",
    accent: "neutral",
    y_min: 0,
    y_max: 20,
    has_target_band: false,
  },
];

function freshnessLabel(data: SensorsCurrent): {
  label: string;
  dotClass: string;
} {
  if (data.stale) {
    return { label: "stale", dotClass: "text-status-warn" };
  }
  return { label: "live", dotClass: "text-status-ok" };
}

function HostedDashboardPage() {
  const [range, setRange] = useState<SparklineRange>("24h");
  const [selectedSiteId, setSelectedSiteId] = useState("homebox");
  const [selectedTentId, setSelectedTentId] = useState("main");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const sitesQuery = useQuery({
    queryKey: ["cloud.sites"],
    queryFn: async () => {
      const { data } = await hostedApi.GET("/api/sites");
      return hostedData(data, "/api/sites");
    },
  });

  const tentsQuery = useQuery({
    queryKey: ["cloud.tents", selectedSiteId],
    queryFn: async () => {
      const { data } = await hostedApi.GET("/api/tents", {
        params: { query: { site_id: selectedSiteId } },
      });
      return hostedData(data, "/api/tents");
    },
    enabled: selectedSiteId.length > 0,
  });

  const stateQuery = useQuery({
    queryKey: ["cloud.tent.state", selectedTentId],
    queryFn: async () => {
      const { data } = await hostedApi.GET("/api/tents/{tent_id}/state", {
        params: { path: { tent_id: selectedTentId } },
      });
      return hostedData(data, "/api/tents/{tent_id}/state");
    },
    enabled: selectedTentId.length > 0,
  });

  const metricsQuery = useQuery({
    queryKey: ["cloud.metrics.current", selectedTentId],
    queryFn: async () => {
      const { data } = await hostedApi.GET("/api/tents/{tent_id}/metrics/current", {
        params: { path: { tent_id: selectedTentId } },
      });
      return hostedData(data, "/api/tents/{tent_id}/metrics/current");
    },
    enabled: selectedTentId.length > 0,
  });

  const historyResults = useQueries({
    queries: HOSTED_METRIC_META.map((m) => ({
      queryKey: ["cloud.metrics.history", selectedTentId, range, m.metric] as const,
      queryFn: async () => {
        const { data } = await hostedApi.GET("/api/tents/{tent_id}/metrics/history", {
          params: {
            path: { tent_id: selectedTentId },
            query: { range, metric: m.metric },
          },
        });
        return hostedData(data, "/api/tents/{tent_id}/metrics/history");
      },
      enabled: selectedTentId.length > 0,
    })),
  });

  const devicesQuery = useQuery({
    queryKey: ["cloud.devices", selectedTentId],
    queryFn: async () => {
      const { data } = await hostedApi.GET("/api/tents/{tent_id}/devices", {
        params: { path: { tent_id: selectedTentId } },
      });
      return hostedData(data, "/api/tents/{tent_id}/devices");
    },
    enabled: selectedTentId.length > 0,
  });

  const lightSchedulesQuery = useQuery({
    queryKey: ["cloud.lights.schedules", selectedTentId],
    queryFn: async () => {
      const { data } = await hostedApi.GET("/api/tents/{tent_id}/lights/schedules", {
        params: { path: { tent_id: selectedTentId } },
      });
      return hostedData(data, "/api/tents/{tent_id}/lights/schedules");
    },
    enabled: selectedTentId.length > 0,
  });

  const assetsQuery = useQuery({
    queryKey: ["cloud.assets.latest", selectedTentId],
    queryFn: async () => {
      const { data } = await hostedApi.GET("/api/tents/{tent_id}/assets/latest", {
        params: { path: { tent_id: selectedTentId } },
      });
      return hostedData(data, "/api/tents/{tent_id}/assets/latest");
    },
    enabled: selectedTentId.length > 0,
    retry: false,
  });

  const syncQuery = useQuery({
    queryKey: ["cloud.sync.status"],
    queryFn: async () => {
      const { data } = await hostedApi.GET("/api/sync/status");
      return hostedData(data, "/api/sync/status");
    },
    refetchInterval: 30_000,
  });

  const sites = sitesQuery.data ?? [];
  const tents = tentsQuery.data ?? [];
  const selectedTent = tents.find((tent) => tent.tent_id === selectedTentId);
  const metrics = metricsQuery.data ?? [];
  const syncStatus = syncQuery.data ?? null;
  const gatewayStatus =
    syncStatus?.status ?? hostedGatewayStatus(syncStatus?.gateway_last_seen_at ?? null);
  const metricCards = toMetricCards(metrics);
  const metricSourceRows = toMetricSourceRows(metrics);
  const assetPanel = toAssetPanelModel(
    assetsQuery.data?.[0] ?? null,
    Boolean(assetsQuery.error),
  );
  const deviceRows = toDeviceRows(devicesQuery.data ?? []);

  const onSiteChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const nextSite = event.currentTarget.value;
    setSelectedSiteId(nextSite);
    setSelectedTentId("main");
  };

  const onTentChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setSelectedTentId(event.currentTarget.value);
  };

  if (sitesQuery.isLoading || tentsQuery.isLoading) {
    return (
      <main className="flex-1 overflow-auto p-6">
        <p className="font-mono text-xs uppercase tracking-caps text-ink-3">
          Loading hosted dashboard…
        </p>
      </main>
    );
  }

  if (sitesQuery.error || tentsQuery.error) {
    return (
      <main className="flex-1 overflow-auto p-6">
        <p className="font-mono text-xs uppercase tracking-caps text-accent-magenta">
          Failed to load hosted scope
        </p>
      </main>
    );
  }

  return (
    <main className="flex-1 overflow-auto">
      <div className="mx-auto flex max-w-350 flex-col gap-6 px-8 pb-16 pt-7">
        <section className="grid gap-4 border-b border-rule-strong pb-4 lg:grid-cols-[1fr_auto]">
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex flex-col gap-1 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              Site
              <select
                value={selectedSiteId}
                onChange={onSiteChange}
                className="border border-rule-strong bg-paper px-3 py-2 font-sans text-fs-12 normal-case tracking-normal text-ink"
              >
                {sites.map((site) => (
                  <option key={site.site_id} value={site.site_id}>
                    {site.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              Tent
              <select
                value={selectedTentId}
                onChange={onTentChange}
                className="border border-rule-strong bg-paper px-3 py-2 font-sans text-fs-12 normal-case tracking-normal text-ink"
              >
                {tents.map((tent) => (
                  <option key={tent.tent_id} value={tent.tent_id}>
                    {tent.name}
                    {tent.is_active ? "" : " (inactive)"}
                  </option>
                ))}
              </select>
            </label>
            <span className="border border-rule px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              Read only
            </span>
          </div>
          <div className="flex flex-wrap items-end justify-start gap-3 lg:justify-end">
            <StatusPill
              label={gatewayStatus}
              value={`Gateway ${formatAge(syncStatus?.gateway_last_seen_at ?? null)}`}
            />
            <StatusPill
              label="backlog"
              value={`${syncStatus?.command_backlog_depth ?? 0} queued`}
            />
            <RangeSwitch value={range} onChange={setRange} />
          </div>
        </section>

        <section className="grid grid-cols-1 gap-3 border border-rule-strong bg-paper-2 p-4 sm:grid-cols-3">
          <HostedFact label="Tent" value={selectedTent?.name ?? selectedTentId} />
          <HostedFact
            label="Catalog"
            value={formatTimestamp(stateQuery.data?.last_catalog_sync_at ?? null)}
          />
          <HostedFact
            label="Gateway seen"
            value={formatTimestamp(syncStatus?.gateway_last_seen_at ?? null)}
          />
        </section>

        <LightSchedulePanel
          schedules={lightSchedulesQuery.data?.schedules ?? []}
          loading={lightSchedulesQuery.isLoading}
        />

        {metricsQuery.isLoading ? (
          <p className="font-mono text-xs uppercase tracking-caps text-ink-3">
            Loading current metrics…
          </p>
        ) : metrics.length === 0 ? (
          <section className="border border-rule-strong bg-paper-2 p-5">
            <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              No synced metrics for this tent yet.
            </p>
          </section>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-px border border-rule-strong bg-rule sm:grid-cols-2 lg:grid-cols-6">
              <section aria-label="Environment gauges" className="contents">
                {metricCards.map((card) => {
                  const formatProp = card.format ? { format: card.format } : {};
                  return (
                    <Gauge
                      key={card.key}
                      name={card.name}
                      value={card.value}
                      unit={card.unit}
                      band={null}
                      status={card.status}
                      accent={card.accent}
                      {...formatProp}
                    />
                  );
                })}
              </section>
            </div>
            <section aria-label="Metric source times" className="bg-paper-2 p-4">
              <h2 className="mb-2 font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
                Metric Source Times
              </h2>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {metricSourceRows.map((metric) => (
                  <HostedFact
                    key={metric.key}
                    label={metric.label}
                    value={metric.value}
                  />
                ))}
              </div>
            </section>
          </>
        )}

        <section aria-label="Environment history" className="flex flex-col">
          <header className="flex items-baseline justify-between border-b border-rule px-0.5 py-2">
            <h2 className="font-sans text-fs-11 font-semibold uppercase tracking-cap-wide text-ink-2">
              History
            </h2>
            <HoverTimestamp
              hoverIndex={hoverIndex}
              points={toSparklinePoints(historyResults.find((r) => r.data)?.data)}
            />
          </header>
          <div className="grid grid-cols-1 border border-rule-strong bg-paper-2 sm:grid-cols-2 lg:grid-cols-3">
            {HOSTED_METRIC_META.map((m, idx) => {
              const result = historyResults[idx];
              const points = toSparklinePoints(result?.data);
              const unit = result?.data?.points[0]?.unit ?? m.unit;
              const yProps = {
                ...(m.y_min !== null && m.y_min !== undefined ? { yMin: m.y_min } : {}),
                ...(m.y_max !== null && m.y_max !== undefined ? { yMax: m.y_max } : {}),
              };
              return (
                <Sparkline
                  key={m.metric}
                  name={m.display_name}
                  points={points}
                  unit={unit ?? ""}
                  accent={asAccent(m.accent)}
                  hoverIndex={hoverIndex}
                  onHoverIndex={setHoverIndex}
                  {...yProps}
                />
              );
            })}
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <HostedAssetsPanel model={assetPanel} />
          <HostedDevicesPanel devices={deviceRows} />
        </section>
      </div>
    </main>
  );
}

function DashboardPage() {
  return isHostedApiMode ? <HostedDashboardPage /> : <LocalDashboardPage />;
}

function LocalDashboardPage() {
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

  const lightSchedulesQuery = useQuery({
    queryKey: ["lights.schedules", "main"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/tents/{tent_id}/lights/schedules", {
        params: { path: { tent_id: "main" } },
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
        <LightSchedulePanel
          schedules={lightSchedulesQuery.data?.schedules ?? []}
          loading={lightSchedulesQuery.isLoading}
        />
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

function StatusPill({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <span className="inline-flex items-center gap-2 border border-rule bg-paper-2 px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
      <span className="text-ink">{label}</span>
      <span>{value}</span>
    </span>
  );
}

function HostedFact({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
        {label}
      </span>
      <span className="truncate font-sans text-fs-13 text-ink">{value}</span>
    </div>
  );
}

function LightSchedulePanel({
  schedules,
  loading,
}: {
  schedules: readonly DashboardLightSchedule[];
  loading: boolean;
}): ReactNode {
  return (
    <section aria-label="Light schedules" className="flex flex-col bg-paper-2 p-4">
      <h2 className="mb-2 font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
        Light Schedule
      </h2>
      {loading ? (
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          Loading light schedule…
        </p>
      ) : schedules.length === 0 ? (
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          No light schedule synced for this tent.
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {schedules.map((schedule) => (
            <div
              key={schedule.schedule_id}
              className="border border-rule bg-paper px-3.5 py-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-sans text-fs-13 font-semibold text-ink">
                    {lightScheduleLabel(schedule)}
                  </p>
                  <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                    {formatScheduleTime(schedule.starts_local)}-
                    {formatScheduleTime(schedule.ends_local)} local
                  </p>
                </div>
                <span className="shrink-0 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                  {formatPhotoperiod(schedule.duration_hours)}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2 font-mono text-fs-10 uppercase tracking-caps">
                <span className={schedule.is_on ? "text-status-ok" : "text-ink-3"}>
                  {schedule.is_on ? "On" : "Off"}
                </span>
                <span className="text-ink-3">{formatNextTransition(schedule)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function HostedAssetsPanel({ model }: { model: AssetPanelModel }): ReactNode {
  return (
    <section
      aria-label="Latest private asset"
      className="flex flex-col gap-3 bg-paper-2 p-4"
    >
      <h2 className="font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
        Latest Asset
      </h2>
      {model.state === "unavailable" ? (
        <p className="font-mono text-fs-10 uppercase tracking-caps text-accent-magenta">
          Signed asset URL unavailable
        </p>
      ) : model.state === "ready" ? (
        <>
          <img
            src={model.imageUrl}
            alt=""
            className="aspect-video w-full border border-rule-strong object-cover"
          />
          <HostedFact label="Captured" value={model.capturedValue} />
        </>
      ) : (
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          No synced assets for this tent.
        </p>
      )}
    </section>
  );
}

function HostedDevicesPanel({
  devices,
}: {
  devices: readonly DeviceRowModel[];
}): ReactNode {
  return (
    <section aria-label="Cloud devices" className="flex flex-col bg-paper-2 p-4">
      <h2 className="mb-2 font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
        Devices
      </h2>
      {devices.length === 0 ? (
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          No devices synced for this tent.
        </p>
      ) : (
        <table className="w-full border-collapse font-sans text-fs-12">
          <thead>
            <tr>
              <th className="border-b border-rule-strong px-3.5 py-1.5 text-left font-sans text-fs-10 font-semibold uppercase tracking-caps text-ink-2">
                Device
              </th>
              <th className="border-b border-rule-strong px-3.5 py-1.5 text-right font-sans text-fs-10 font-semibold uppercase tracking-caps text-ink-2">
                Last seen
              </th>
            </tr>
          </thead>
          <tbody>
            {devices.map((device) => (
              <tr key={device.id} className="border-b border-rule last:border-b-0">
                <td className="px-3.5 py-2.5 text-ink">
                  {device.name}
                  <span className="ml-2 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                    {device.kindLabel}
                  </span>
                </td>
                <td className="px-3.5 py-2.5 text-right font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                  {device.lastSeenLabel}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function toMetricCards(metrics: readonly HostedMetric[]): readonly MetricCardModel[] {
  const metricsByName = new Map(metrics.map((metric) => [metric.metric, metric]));
  return HOSTED_METRIC_META.flatMap((meta) => {
    const metric = metricsByName.get(meta.metric);
    if (!metric) return [];
    const card = {
      accent: asAccent(meta.accent),
      key: meta.metric,
      name: meta.display_name,
      status: toMetricStatus(metric),
      unit: metric.unit ?? meta.unit,
      value: metric.value,
    };
    return isIntegerMetric(meta) ? [{ ...card, format: formatInteger }] : [card];
  });
}

function toMetricSourceRows(
  metrics: readonly HostedMetric[],
): readonly MetricSourceModel[] {
  return metrics.map((metric) => ({
    key: `${metric.capability_id}:${metric.metric}`,
    label: displayMetricName(metric.metric),
    value: `${formatTimestamp(metric.source_updated_at)} · ${toMetricFreshness(metric)}`,
  }));
}

function toAssetPanelModel(
  asset: HostedAsset | null,
  unavailable: boolean,
): AssetPanelModel {
  if (unavailable) return { state: "unavailable" };
  if (asset === null) return { state: "empty" };
  return {
    state: "ready",
    capturedValue: `${formatTimestamp(asset.captured_at)} · expires ${formatTimestamp(asset.signed_url_expires_at)}`,
    imageUrl: asset.signed_url,
  };
}

function toDeviceRows(devices: readonly HostedDevice[]): readonly DeviceRowModel[] {
  return devices.map((device) => ({
    id: device.device_id,
    kindLabel: device.is_active ? device.kind : "inactive",
    lastSeenLabel: formatAge(device.last_seen_at),
    name: device.name,
  }));
}

function toMetricStatus(metric: HostedMetric): MetricStatus {
  return toMetricFreshness(metric) === "live" ? "ok" : "warn";
}

function toMetricFreshness(metric: HostedMetric): MetricFreshness {
  const sourceMs = Date.parse(metric.source_updated_at);
  if (!Number.isFinite(sourceMs)) return "stale";
  return Date.now() - sourceMs > metric.stale_after_s * 1000 ? "stale" : "live";
}

function hostedGatewayStatus(lastSeenAt: string | null): HostedSyncStatus["status"] {
  if (lastSeenAt === null) return "offline";
  const ageMs = Date.now() - Date.parse(lastSeenAt);
  if (!Number.isFinite(ageMs)) return "offline";
  if (ageMs > 5 * 60_000) return "offline";
  if (ageMs > 90_000) return "stale";
  return "live";
}

function displayMetricName(metric: string): string {
  return (
    HOSTED_METRIC_META.find((item) => item.metric === metric)?.display_name ?? metric
  );
}

function lightScheduleLabel(schedule: DashboardLightSchedule): string {
  if (schedule.device_id === null) return schedule.schedule_id;
  return schedule.device_id
    .replace(/^kasa-lights-/, "")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatScheduleTime(value: string): string {
  return value.slice(0, 5);
}

function formatPhotoperiod(durationHours: number): string {
  const onHours = Math.round(durationHours * 10) / 10;
  const offHours = Math.round((24 - durationHours) * 10) / 10;
  return `${formatHourCount(onHours)}/${formatHourCount(offHours)}`;
}

function formatHourCount(value: number): string {
  return Number.isInteger(value) ? `${value}` : `${value.toFixed(1)}`;
}

function formatNextTransition(schedule: DashboardLightSchedule): string {
  const minutes = schedule.is_on
    ? schedule.minutes_until_off
    : schedule.minutes_until_on;
  return `${schedule.is_on ? "off" : "on"} in ${formatMinutes(minutes)}`;
}

function formatMinutes(value: number): string {
  const total = Math.max(0, Math.round(value));
  const hours = Math.floor(total / 60);
  const minutes = total % 60;
  if (hours === 0) return `${minutes}m`;
  if (minutes === 0) return `${hours}h`;
  return `${hours}h ${minutes}m`;
}

function formatTimestamp(value: string | null): string {
  if (value === null) return "never";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "unknown";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function formatAge(value: string | null): string {
  if (value === null) return "never";
  const then = Date.parse(value);
  if (!Number.isFinite(then)) return "unknown";
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.round(minutes / 60)}h ago`;
}

function toSparklinePoints(
  history: HostedMetricHistory | undefined,
): components["schemas"]["HistoryPoint"][] {
  return (
    history?.points.map((point) => ({
      ts: point.bucket_start_at,
      value: point.avg ?? point.max ?? point.min ?? 0,
    })) ?? []
  );
}
