// Hosted dashboard route (/) — synced tent metrics, assets, devices,
// light schedules, and gateway status from the Railway control plane.
import { useQueries, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import type { ChangeEvent, ReactNode } from "react";
import { useState } from "react";
import { createHostedApiClient, type hostedComponents } from "@/api-client";
import { formatMetricValue } from "@/shared/metricFormat";
import { Gauge } from "@/ui/Gauge";
import { HoverTimestamp } from "@/ui/HoverTimestamp";
import { formatEmptyHistoryLabel } from "@/ui/historyRangeLabels";
import { PlantSticker } from "@/ui/PlantSticker";
import { RangeSwitch, type SparklineRange } from "@/ui/RangeSwitch";
import { Sparkline } from "@/ui/Sparkline";

export const Route = createFileRoute("/")({
  component: HostedDashboardPage,
});

const hostedApi = createHostedApiClient();
const PLANT_DETAIL_ROUTE = "/tents/$tentId/plants/$plantId" as const;
const LIVE_DASHBOARD_REFETCH_MS = 30_000;

type SparklineAccent =
  | "temp"
  | "humidity"
  | "vpd"
  | "moisture"
  | "reservoir"
  | "neutral";
type MetricStatus = "ok" | "warn" | "crit";
type HostedAsset = hostedComponents["schemas"]["AssetResponse"];
type HostedDevice = hostedComponents["schemas"]["DeviceResponse"];
type HostedLightSchedule = hostedComponents["schemas"]["LightScheduleResponse"];
type HostedMetric = hostedComponents["schemas"]["CurrentMetricResponse"];
type HostedMetricHistory = hostedComponents["schemas"]["MetricHistoryResponse"];
type HostedMetricPresentation =
  hostedComponents["schemas"]["MetricPresentationMetricResponse"];
type HostedPlant = hostedComponents["schemas"]["PlantSummaryResponse"];
type HostedSyncStatus = hostedComponents["schemas"]["SyncStatusResponse"];
type DashboardLightSchedule = HostedLightSchedule;
type HistoryPoint = {
  ts: string;
  value: number | null;
};
type MetricFreshness = "live" | "stale";
type MetricCardModel = {
  accent: SparklineAccent;
  key: string;
  name: string;
  status: MetricStatus;
  unit: string;
  value: number;
  valuePrecision: number;
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
  "reservoir",
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

function formatInteger(value: number): string {
  return `${Math.round(value)}`;
}

function HostedDashboardPage() {
  const [range, setRange] = useState<SparklineRange>("24h");
  const [selectedSiteId, setSelectedSiteId] = useState("homebox");
  const [selectedTentId, setSelectedTentId] = useState("main");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [hoverTimestamp, setHoverTimestamp] = useState<string | null>(null);

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
    refetchInterval: LIVE_DASHBOARD_REFETCH_MS,
  });

  const presentationQuery = useQuery({
    queryKey: ["cloud.metrics.presentation", selectedTentId],
    queryFn: async () => {
      const { data } = await hostedApi.GET(
        "/api/tents/{tent_id}/metrics/presentation",
        {
          params: { path: { tent_id: selectedTentId } },
        },
      );
      return hostedData(data, "/api/tents/{tent_id}/metrics/presentation");
    },
    enabled: selectedTentId.length > 0,
  });

  const plantsQuery = useQuery({
    queryKey: ["cloud.plants", selectedTentId],
    queryFn: async () => {
      const { data } = await hostedApi.GET("/api/tents/{tent_id}/plants", {
        params: { path: { tent_id: selectedTentId } },
      });
      return hostedData(data, "/api/tents/{tent_id}/plants");
    },
    enabled: selectedTentId.length > 0,
  });

  const historyGroups = presentationQuery.data?.history_groups ?? [];
  const historyMetrics = historyGroups.flatMap((group) => group.metrics);
  const historyResults = useQueries({
    queries: historyMetrics.map((m) => ({
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
      enabled: selectedTentId.length > 0 && presentationQuery.isSuccess,
      refetchInterval: range === "1h" ? LIVE_DASHBOARD_REFETCH_MS : false,
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
  const plants = plantsQuery.data ?? [];
  const syncStatus = syncQuery.data ?? null;
  const gatewayStatus =
    syncStatus?.status ?? hostedGatewayStatus(syncStatus?.gateway_last_seen_at ?? null);
  const metricCards = toMetricCards(
    metrics,
    presentationQuery.data?.current_metrics ?? [],
  );
  const historyByMetric = new Map(
    historyMetrics.map((m, idx) => [m.metric, historyResults[idx]]),
  );
  const historyAxis = buildHistoryAxis(historyResults.map((result) => result.data));
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
      <div className="mx-auto flex max-w-350 flex-col gap-5 px-5 pb-14 pt-5 sm:px-8 sm:pb-16 sm:pt-7">
        <section className="grid gap-3 border-b border-rule-strong pb-4 lg:grid-cols-[1fr_auto]">
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              Site
              <select
                value={selectedSiteId}
                onChange={onSiteChange}
                className="min-w-28 border border-rule-strong bg-paper px-3 py-2 font-sans text-fs-12 normal-case tracking-normal text-ink"
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
                className="min-w-32 border border-rule-strong bg-paper px-3 py-2 font-sans text-fs-12 normal-case tracking-normal text-ink"
              >
                {tents.map((tent) => (
                  <option key={tent.tent_id} value={tent.tent_id}>
                    {tent.name}
                    {tent.is_active ? "" : " (inactive)"}
                  </option>
                ))}
              </select>
            </label>
            <span className="border border-rule bg-paper-2 px-2.5 py-2 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              Read only
            </span>
          </div>
          <div className="flex flex-wrap items-end justify-start gap-2 lg:justify-end">
            <StatusPill
              tone={gatewayStatus}
              label={gatewayStatus}
              value={`Gateway ${formatAge(syncStatus?.gateway_last_seen_at ?? null)}`}
            />
            <StatusPill
              tone={syncStatus?.command_backlog_depth ? "warn" : "ok"}
              label="backlog"
              value={`${syncStatus?.command_backlog_depth ?? 0} queued`}
            />
          </div>
        </section>

        <section className="grid grid-cols-1 gap-px border border-rule-strong bg-rule sm:grid-cols-3">
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

        {metricsQuery.isLoading || presentationQuery.isLoading ? (
          <p className="font-mono text-xs uppercase tracking-caps text-ink-3">
            Loading current metrics…
          </p>
        ) : metricsQuery.error || presentationQuery.error ? (
          <section className="border border-rule-strong bg-paper-2 p-5">
            <p className="font-mono text-fs-10 uppercase tracking-caps text-accent-magenta">
              Failed to load metric presentation.
            </p>
          </section>
        ) : metrics.length === 0 || metricCards.length === 0 ? (
          <section className="border border-rule-strong bg-paper-2 p-5">
            <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              No synced metrics for this tent yet.
            </p>
          </section>
        ) : (
          <div className="grid grid-cols-1 gap-px border border-rule-strong bg-rule sm:grid-cols-2 md:grid-cols-4 xl:grid-cols-7">
            <section aria-label="Environment gauges" className="contents">
              {metricCards.map((card) => (
                <Gauge
                  key={card.key}
                  name={card.name}
                  value={card.value}
                  unit={card.unit}
                  band={null}
                  status={card.status}
                  accent={card.accent}
                  format={(value) => formatMetricValue(value, card.valuePrecision)}
                />
              ))}
            </section>
          </div>
        )}

        <HostedPlantsPanel
          plants={plants}
          tentId={selectedTentId}
          loading={plantsQuery.isLoading}
        />

        <section aria-label="Metric history" className="flex flex-col">
          <header className="sticky top-0 z-20 flex flex-col gap-2 border-b border-rule bg-paper/95 px-0.5 py-2 backdrop-blur sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-h-7 items-baseline justify-between gap-3">
              <h2 className="font-sans text-fs-11 font-semibold uppercase tracking-cap-wide text-ink-2">
                History
              </h2>
              <HoverTimestamp
                hoverIndex={hoverIndex}
                points={historyAxis.map((ts) => ({ ts }))}
                timestamp={hoverTimestamp}
              />
            </div>
            <RangeSwitch value={range} onChange={setRange} />
          </header>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {historyGroups.map((group) => (
              <section
                key={group.group}
                aria-label={`${group.label} history`}
                className="flex min-w-0 flex-col"
              >
                <h3 className="border-x border-t border-rule-strong bg-paper-2 px-3.5 py-2 font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
                  {group.label}
                </h3>
                <div className="grid grid-cols-1 border border-rule-strong bg-paper-2">
                  {group.metrics.map((m) => {
                    const result = historyByMetric.get(m.metric);
                    const points = result?.data
                      ? toSparklinePoints(result.data, historyAxis)
                      : [];
                    const unit = result?.data?.points[0]?.unit ?? m.unit;
                    const yProps = {
                      ...(m.y_min !== null && m.y_min !== undefined
                        ? { yMin: m.y_min }
                        : {}),
                      ...(m.y_max !== null && m.y_max !== undefined
                        ? { yMax: m.y_max }
                        : {}),
                    };
                    return (
                      <Sparkline
                        key={m.metric}
                        name={m.display_name}
                        points={points}
                        unit={unit ?? ""}
                        accent={asAccent(m.accent)}
                        valuePrecision={m.value_precision}
                        emptyLabel={
                          result?.isLoading
                            ? "Loading data"
                            : formatEmptyHistoryLabel(range)
                        }
                        hoverIndex={hoverIndex}
                        onHoverIndex={setHoverIndex}
                        onHoverPoint={(point) => {
                          setHoverTimestamp(point?.ts ?? null);
                        }}
                        {...yProps}
                      />
                    );
                  })}
                </div>
              </section>
            ))}
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

function StatusPill({
  label,
  tone,
  value,
}: {
  label: string;
  tone: "live" | "stale" | "offline" | "ok" | "warn";
  value: string;
}): ReactNode {
  const dotClass =
    tone === "live" || tone === "ok"
      ? "bg-status-ok"
      : tone === "stale" || tone === "warn"
        ? "bg-status-warn"
        : "bg-status-err";
  return (
    <span className="inline-flex items-center gap-2 border border-rule bg-paper-2 px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
      <span aria-hidden="true" className={`h-1.5 w-1.5 ${dotClass}`} />
      <span className="text-ink">{label}</span>
      <span>{value}</span>
    </span>
  );
}

function HostedFact({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <div className="flex min-w-0 flex-col gap-1 bg-paper-2 p-3 sm:p-4">
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
    <section
      aria-label="Light schedules"
      className="border border-rule bg-paper-2 px-4 py-3"
    >
      <header className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
          Light Schedule
        </h2>
        <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          {formatScheduleCount(schedules.length)}
        </span>
      </header>
      {loading ? (
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          Loading light schedule…
        </p>
      ) : schedules.length === 0 ? (
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          No light schedule synced for this tent.
        </p>
      ) : (
        <div className="grid gap-2">
          {schedules.map((schedule) => (
            <div
              key={schedule.schedule_id}
              className="grid gap-3 border border-rule bg-paper px-3.5 py-3 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center sm:gap-5"
            >
              <div className="min-w-0 space-y-1">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <p className="truncate font-sans text-fs-13 font-semibold text-ink">
                    {lightScheduleLabel(schedule)}
                  </p>
                  <LightStatePill isOn={schedule.is_on} />
                </div>
                <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                  {formatNextTransition(schedule)}
                </p>
              </div>
              <div className="space-y-1 font-mono text-fs-10 uppercase tracking-caps">
                <p className="text-ink-3">Photoperiod</p>
                <p className="text-ink">{formatPhotoperiod(schedule.duration_hours)}</p>
              </div>
              <div className="space-y-1 font-mono text-fs-10 uppercase tracking-caps sm:text-right">
                <p className="text-ink-3">Daily window</p>
                <p className="text-ink">
                  {formatScheduleTime(schedule.starts_local)}-
                  {formatScheduleTime(schedule.ends_local)} local
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function LightStatePill({ isOn }: { isOn: boolean }): ReactNode {
  return (
    <span
      className={
        isOn
          ? "inline-flex border border-status-ok bg-status-ok px-2 py-1 font-mono text-fs-10 uppercase tracking-caps text-paper"
          : "inline-flex border border-rule-strong bg-paper-2 px-2 py-1 font-mono text-fs-10 uppercase tracking-caps text-ink"
      }
    >
      {isOn ? "On now" : "Off now"}
    </span>
  );
}

function HostedPlantsPanel({
  loading,
  plants,
  tentId,
}: {
  loading: boolean;
  plants: readonly HostedPlant[];
  tentId: string;
}): ReactNode {
  return (
    <section
      aria-label="Plant moisture"
      className="border border-rule bg-paper-2 px-4 py-3"
    >
      <header className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
          Plant Moisture
        </h2>
        <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          {formatPlantCount(plants.length)}
        </span>
      </header>
      {loading ? (
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          Loading plants…
        </p>
      ) : plants.length === 0 ? (
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          No plants synced for this tent.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {plants.map((plant) =>
            plant.has_moisture_stream ? (
              <Link
                key={plant.plant_id}
                to={PLANT_DETAIL_ROUTE}
                params={{ tentId, plantId: plant.plant_id }}
                className="group min-w-0 border border-rule bg-paper px-3.5 py-3 transition hover:border-rule-strong"
              >
                <PlantRowContent plant={plant} linked />
              </Link>
            ) : (
              <div
                key={plant.plant_id}
                className="min-w-0 border border-rule bg-paper px-3.5 py-3 opacity-75"
              >
                <PlantRowContent plant={plant} linked={false} />
              </div>
            ),
          )}
        </div>
      )}
    </section>
  );
}

function PlantRowContent({
  linked,
  plant,
}: {
  linked: boolean;
  plant: HostedPlant;
}): ReactNode {
  const moistureValue = plant.latest_moisture?.value ?? null;
  const moisturePercent =
    moistureValue === null ? null : Math.max(0, Math.min(100, moistureValue));
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <PlantSticker color={plant.sticker_color} size="sm" />
            <p className="truncate font-sans text-fs-13 font-semibold text-ink">
              {plant.name}
            </p>
          </div>
          <p className="mt-1 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            {plant.status} · target {formatMoistureTarget(plant)}
          </p>
        </div>
        <span className="shrink-0 font-mono text-fs-12 tabular-nums text-ink">
          {moistureValue === null ? "No reading" : formatMoistureValue(moistureValue)}
        </span>
      </div>
      <div className="h-2 border border-rule bg-paper-2">
        {moisturePercent === null ? (
          <div className="h-full bg-[repeating-linear-gradient(90deg,var(--color-rule)_0,var(--color-rule)_2px,transparent_2px,transparent_6px)]" />
        ) : (
          <div
            // eslint-disable-next-line no-restricted-syntax -- data-driven bar width is not expressible in build-time Tailwind classes
            style={{ width: `${moisturePercent}%` }}
            className="h-full bg-sensor-moisture"
          />
        )}
      </div>
      {linked ? null : (
        <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          No moisture stream
        </span>
      )}
    </div>
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

function toMetricCards(
  metrics: readonly HostedMetric[],
  presentations: readonly HostedMetricPresentation[],
): readonly MetricCardModel[] {
  const metricsByName = new Map(metrics.map((metric) => [metric.metric, metric]));
  return presentations.flatMap((presentation) => {
    const metric = metricsByName.get(presentation.metric);
    if (!metric) return [];
    return [
      {
        accent: asAccent(presentation.accent),
        key: presentation.metric,
        name: presentation.display_name,
        status: toMetricStatus(metric),
        unit: presentation.unit,
        value: metric.value,
        valuePrecision: presentation.value_precision,
      },
    ];
  });
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
  return `${formatHourCount(onHours)} on / ${formatHourCount(offHours)} off`;
}

function formatScheduleCount(count: number): string {
  return `${count} schedule${count === 1 ? "" : "s"}`;
}

function formatPlantCount(count: number): string {
  return `${count} plant${count === 1 ? "" : "s"}`;
}

function formatHourCount(value: number): string {
  return `${Number.isInteger(value) ? value : value.toFixed(1)}h`;
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

function formatMoistureTarget(plant: HostedPlant): string {
  return `${formatInteger(plant.moisture_target_low)}-${formatInteger(
    plant.moisture_target_high,
  )}%`;
}

function formatMoistureValue(value: number): string {
  return `${formatInteger(value)}%`;
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

function buildHistoryAxis(
  histories: readonly (HostedMetricHistory | undefined)[],
): string[] {
  const timestamps = new Set<string>();
  for (const history of histories) {
    for (const point of history?.points ?? []) {
      timestamps.add(point.bucket_start_at);
    }
  }
  return [...timestamps].sort(compareIsoTimestamps);
}

function compareIsoTimestamps(a: string, b: string): number {
  return new Date(a).getTime() - new Date(b).getTime();
}

function toSparklinePoints(
  history: HostedMetricHistory,
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
