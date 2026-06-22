import {
  type QueryClient,
  queryOptions,
  useQueryClient,
  useSuspenseQueries,
} from "@tanstack/react-query";
import { createHostedApiClient, type hostedComponents } from "@/api-client";
import { invalidateSeedLotReads, type SeedLotSexTypeKey } from "@/shared/seedLots";
import type {
  PlantDetail,
  PlantListResult,
  PlantMetricHistory,
  PlantRow,
  PlantSexKey,
  PlantStageKey,
  PlantsBootstrap,
  PlantTelemetryStream,
} from "./plantsTypes";

const hostedApi = createHostedApiClient();
const PLANT_DETAIL_API_PATH = "/api/breeding-logbook/plants/{plant_key}" as const;
const PLANT_METRIC_HISTORY_API_PATH =
  "/api/breeding-logbook/plants/{plant_key}/metrics/history" as const;

type HostedPlantsBootstrap =
  hostedComponents["schemas"]["BreedingLogbookBootstrapResponse"];
type HostedPlantsPlantList =
  hostedComponents["schemas"]["BreedingLogbookPlantListResponse"];
type HostedPlantsPlantDetail =
  hostedComponents["schemas"]["BreedingLogbookPlantDetailResponse"];
type HostedPlantMetricHistory =
  hostedComponents["schemas"]["PlantMetricHistoryResponse"];

const plantsQueryKeys = {
  bootstrap: ["plants", "bootstrap"],
  plants: ["plants", "list"],
  plantDetail: (plantKey: string) => ["plants", plantKey || "first", "detail"],
} as const;

export function invalidatePlantsReads(
  queryClient: QueryClient,
  plantKeys: readonly string[] = [],
): void {
  void queryClient.invalidateQueries({
    queryKey: plantsQueryKeys.bootstrap,
  });
  invalidateSeedLotReads(queryClient);
  void queryClient.invalidateQueries({
    queryKey: plantsQueryKeys.plants,
  });
  for (const plantKey of plantKeys) {
    void queryClient.invalidateQueries({
      queryKey: plantsQueryKeys.plantDetail(plantKey),
    });
  }
}

async function fetchPlantsBootstrap(): Promise<PlantsBootstrap> {
  const { data } = await hostedApi.GET("/api/breeding-logbook/bootstrap");
  return mapBootstrap(hostedData(data, "/api/breeding-logbook/bootstrap"));
}

async function fetchPlantsPlants(): Promise<PlantListResult> {
  const { data } = await hostedApi.GET("/api/breeding-logbook/plants", {
    params: { query: { include_culled: true, group_by: "stage" } },
  });
  return mapPlantList(hostedData(data, "/api/breeding-logbook/plants"));
}

async function fetchPlantsPlantDetail(
  plantKey: string,
  queryClient: QueryClient,
): Promise<PlantDetail> {
  const resolvedPlantKey =
    plantKey ||
    (await queryClient.ensureQueryData(plantsPlantsOptions())).plants[0]?.key;
  if (!resolvedPlantKey) {
    throw new Error("No plants are available to select");
  }
  const [detailResponse, historyResponse] = await Promise.all([
    hostedApi.GET(PLANT_DETAIL_API_PATH, {
      params: { path: { plant_key: resolvedPlantKey } },
    }),
    hostedApi.GET(PLANT_METRIC_HISTORY_API_PATH, {
      params: {
        path: { plant_key: resolvedPlantKey },
        query: { range: "24h" },
      },
    }),
  ]);
  return mapPlantDetail(
    hostedData(detailResponse.data, PLANT_DETAIL_API_PATH),
    hostedData(historyResponse.data, PLANT_METRIC_HISTORY_API_PATH),
  );
}

function plantsBootstrapOptions() {
  return queryOptions({
    queryKey: plantsQueryKeys.bootstrap,
    queryFn: fetchPlantsBootstrap,
    staleTime: Infinity,
  });
}

function plantsPlantsOptions() {
  return queryOptions({
    queryKey: plantsQueryKeys.plants,
    queryFn: fetchPlantsPlants,
    staleTime: Infinity,
  });
}

function plantsPlantDetailOptions(plantKey: string, queryClient: QueryClient) {
  return queryOptions({
    queryKey: plantsQueryKeys.plantDetail(plantKey),
    queryFn: () => fetchPlantsPlantDetail(plantKey, queryClient),
    staleTime: Infinity,
  });
}

export function usePlantsQueries(plantKey: string) {
  const queryClient = useQueryClient();
  return useSuspenseQueries({
    queries: [
      plantsBootstrapOptions(),
      plantsPlantsOptions(),
      plantsPlantDetailOptions(plantKey, queryClient),
    ],
    combine: ([bootstrap, plants, detail]) => ({
      bootstrap: bootstrap.data,
      plants: plants.data,
      detail: detail.data,
    }),
  });
}

function hostedData<T>(data: T | undefined, path: string): T {
  if (data === undefined) {
    throw new Error(`${path} returned no data`);
  }
  return data;
}

export function mapBootstrap(response: HostedPlantsBootstrap): PlantsBootstrap {
  return {
    today: response.today,
    todayLabel: response.today_label,
    plantSexes: response.plant_sexes.map((row) => ({
      key: toPlantSexKey(row.key),
      displayName: row.display_name,
      displayOrder: row.display_order,
    })),
    seedLotSexTypes: response.seed_lot_sex_types.map((row) => ({
      key: toSeedLotSexTypeKey(row.key),
      displayName: row.display_name,
      displayOrder: row.display_order,
    })),
    stages: response.stages.map((row) => ({
      key: toPlantStageKey(row.key),
      displayName: row.display_name,
      displayOrder: row.display_order,
    })),
    locations: response.locations.map((row) => ({
      sourceTentId: row.source_tent_id,
      displayName: row.display_name,
      role: row.role,
    })),
  };
}

export function mapPlantList(response: HostedPlantsPlantList): PlantListResult {
  return {
    activeCount: response.active_count,
    culledCount: response.culled_count,
    plants: response.plants.map(mapPlantRow),
  };
}

export function mapPlantDetail(
  detail: HostedPlantsPlantDetail,
  metricHistory: HostedPlantMetricHistory,
): PlantDetail {
  return {
    plant: mapPlantRow(detail.plant),
    lineage: {
      parents: detail.lineage.parents,
      offspring: detail.lineage.offspring,
    },
    metrics: detail.metrics.map((metric) => ({
      label: metric.label,
      value: metric.value,
      tone: metric.tone,
    })),
    metricHistory: metricHistory.streams.flatMap(mapMetricHistory),
    telemetry: detail.telemetry.map(mapTelemetryStream),
    wikiContent:
      detail.wiki_content === null
        ? null
        : {
            bodyMarkdown: detail.wiki_content.body_markdown,
            sourceUpdatedAt: detail.wiki_content.source_updated_at,
            title: detail.wiki_content.title,
          },
    events: detail.events.map((event) => ({
      id: event.id,
      dateLabel: event.date_label,
      tag: event.tag,
      body: event.body,
      hasPhoto: event.has_photo,
    })),
  };
}

function mapTelemetryStream(
  stream: HostedPlantsPlantDetail["telemetry"][number],
): PlantTelemetryStream {
  return {
    accent: stream.accent,
    capabilityId: stream.capability_id,
    deviceId: stream.device_id,
    displayName: stream.display_name,
    displayUnit: stream.display_unit,
    historyEnabled: stream.history_enabled,
    key: `${stream.device_id}:${stream.capability_id}:${stream.metric}`,
    latestReading:
      stream.latest_reading === null
        ? null
        : {
            receivedAt: stream.latest_reading.received_at,
            value: stream.latest_reading.value,
          },
    metric: stream.metric,
    valuePrecision: stream.value_precision,
    yMax: stream.y_max,
    yMin: stream.y_min,
  };
}

function mapPlantRow(plant: HostedPlantsPlantList["plants"][number]): PlantRow {
  return {
    id: plant.id,
    key: plant.key,
    name: plant.name,
    strain: plant.strain,
    generation: plant.generation,
    parentsLabel: plant.parents_label,
    sexKey: plant.sex_key,
    stageKey: plant.stage_key,
    stageDay: plant.stage_day,
    isClone: plant.is_clone ?? false,
    germinatedAt: plant.germinated_at ?? null,
    germinatedOn: plant.germinated_on,
    takenAt: plant.taken_at ?? null,
    takenOn: plant.taken_on,
    rootedAt: plant.rooted_at ?? null,
    rootedOn: plant.rooted_on,
    vegStartedAt: plant.veg_started_at ?? null,
    vegStartedOn: plant.veg_started_on,
    flowerStartedAt: plant.flower_started_at ?? null,
    flowerStartedOn: plant.flower_started_on,
    culledOn: plant.culled_on,
    currentTentId: plant.current_tent_id,
    currentTentName: plant.current_tent_name,
    gridPosition: plant.grid_position,
    seedLotLabel: plant.seed_lot_label,
    lastNote: plant.last_note,
    telemetrySummary: plant.telemetry_summary,
  };
}

function mapMetricHistory(
  stream: HostedPlantMetricHistory["streams"][number],
): readonly PlantMetricHistory[] {
  const key = metricHistoryKey(stream.metric);
  if (key === null) return [];
  const points = stream.points.flatMap((point) => {
    const value = point.avg ?? point.max ?? point.min;
    return value === null ? [] : [value];
  });
  return [
    {
      key,
      label: stream.display_name,
      value: formatHistoryValue(points.at(-1), stream.value_precision),
      unit: stream.display_unit,
      tone: "ok",
      points,
    },
  ];
}

function metricHistoryKey(metric: string): PlantMetricHistory["key"] | null {
  switch (metric) {
    case "soil_moisture_pct":
      return "moisture";
    case "substrate_ec_us_cm":
      return "ec";
    case "substrate_ph":
      return "ph";
    case "substrate_temp_c":
      return "temperature";
    default:
      return null;
  }
}

function formatHistoryValue(value: number | undefined, precision: number): string {
  if (value === undefined) return "";
  return value.toFixed(precision);
}

function toPlantSexKey(key: string): PlantSexKey {
  switch (key) {
    case "unknown":
    case "male":
    case "female":
    case "herm":
    case "reversed":
      return key;
    default:
      throw new Error(`Unsupported plant sex key: ${key}`);
  }
}

function toSeedLotSexTypeKey(key: string): SeedLotSexTypeKey {
  switch (key) {
    case "unknown":
    case "feminized":
    case "regular":
      return key;
    default:
      throw new Error(`Unsupported seed lot sex type key: ${key}`);
  }
}

function toPlantStageKey(key: string): PlantStageKey {
  switch (key) {
    case "germinating":
    case "veg":
    case "flower":
    case "breeding":
    case "harvested":
    case "culled":
      return key;
    default:
      throw new Error(`Unsupported plant stage key: ${key}`);
  }
}
