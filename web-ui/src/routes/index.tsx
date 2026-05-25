// Hosted dashboard route (/) — synced tent metrics, assets, devices,
// light schedules, and gateway status from the Railway control plane.
import { useQueries, useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import type { ChangeEvent, ReactNode } from "react";
import { useState } from "react";
import { createHostedApiClient, type hostedComponents } from "@/api-client";
import { Gauge } from "@/ui/Gauge";
import { HoverTimestamp } from "@/ui/HoverTimestamp";
import { RangeSwitch, type SparklineRange } from "@/ui/RangeSwitch";
import { Sparkline } from "@/ui/Sparkline";

export const Route = createFileRoute("/")({
  component: HostedDashboardPage,
});

const hostedApi = createHostedApiClient();

type SparklineAccent = "temp" | "humidity" | "vpd" | "moisture" | "neutral";
type MetricStatus = "ok" | "warn" | "crit";
type HostedAsset = hostedComponents["schemas"]["AssetResponse"];
type HostedDevice = hostedComponents["schemas"]["DeviceResponse"];
type HostedLightSchedule = hostedComponents["schemas"]["LightScheduleResponse"];
type HostedMetric = hostedComponents["schemas"]["CurrentMetricResponse"];
type HostedMetricHistory = hostedComponents["schemas"]["MetricHistoryResponse"];
type HostedSyncStatus = hostedComponents["schemas"]["SyncStatusResponse"];
type DashboardLightSchedule = HostedLightSchedule;
type MetricMeta = {
  metric: string;
  display_name: string;
  unit: string;
  accent: SparklineAccent;
  y_min: number;
  y_max: number;
  has_target_band: boolean;
};
type HistoryPoint = {
  ts: string;
  value: number;
};
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
    y_max: 30,
    has_target_band: false,
  },
  {
    metric: "heater_intensity_pct",
    display_name: "Heat",
    unit: "%",
    accent: "temp",
    y_min: 0,
    y_max: 100,
    has_target_band: false,
  },
];

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
            <RangeSwitch value={range} onChange={setRange} />
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
          <div className="grid grid-cols-1 gap-px border border-rule-strong bg-rule sm:grid-cols-2 md:grid-cols-4 xl:grid-cols-7">
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
              className="grid gap-2 border border-rule bg-paper px-3.5 py-3 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center sm:gap-4"
            >
              <div className="min-w-0">
                <p className="truncate font-sans text-fs-13 font-semibold text-ink">
                  {lightScheduleLabel(schedule)}
                </p>
                <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                  {formatScheduleTime(schedule.starts_local)}-
                  {formatScheduleTime(schedule.ends_local)} local
                </p>
              </div>
              <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                {formatPhotoperiod(schedule.duration_hours)}
              </span>
              <div className="flex flex-wrap items-center gap-2 font-mono text-fs-10 uppercase tracking-caps sm:justify-end">
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
  return `${formatHourCount(onHours)}/${formatHourCount(offHours)}`;
}

function formatScheduleCount(count: number): string {
  return `${count} schedule${count === 1 ? "" : "s"}`;
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

function toSparklinePoints(history: HostedMetricHistory | undefined): HistoryPoint[] {
  return (
    history?.points.map((point) => ({
      ts: point.bucket_start_at,
      value: point.avg ?? point.max ?? point.min ?? 0,
    })) ?? []
  );
}
