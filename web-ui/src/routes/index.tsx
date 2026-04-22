// Dashboard route (/) — five-gauge tile grid.
//
// Fetches /api/sensors/current via TanStack Query. MSW intercepts the
// request in dev + e2e tests (see web-ui/src/mocks/handlers.ts); in
// production the same call hits the real backend on :8001. No
// re-derivation of band_status happens here — the envelope's `status`
// field is the authoritative value the backend stamps onto each
// reading (see apps/shared/src/dirt_shared/services/grow_state.py).
//
// useQuery over a route loader keeps the route component purely
// declarative and lets React Query manage retries + background
// refetches uniformly across the SPA. See
// docs/references/tanstack-router-v1/loaders.md for the loader
// alternative if a future change needs SSR-style prefetch.
import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { type components, createDirtApiClient } from "@/api-client";
import { Gauge } from "@/ui/Gauge";

export const Route = createFileRoute("/")({
  component: DashboardPage,
});

const api = createDirtApiClient();

type SensorsCurrent = components["schemas"]["SensorsCurrent"];
type MetricEnvelope = components["schemas"]["MetricEnvelope"];

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
    </main>
  );
}
