import {
  type QueryClient,
  queryOptions,
  useQueryClient,
  useSuspenseQueries,
} from "@tanstack/react-query";
import { createHostedApiClient, type hostedComponents } from "@/api-client";
import type {
  BreedingLogbookBootstrap,
  PlantDetail,
  PlantListResult,
  PlantMetricHistory,
  PlantRow,
  PlantSexKey,
  PlantStageKey,
  SeedLotListResult,
  SeedLotSexTypeKey,
} from "./breedingLogbookTypes";

const hostedApi = createHostedApiClient();
const BREEDING_LOGBOOK_PLANT_DETAIL_PATH =
  "/api/breeding-logbook/plants/{plant_key}" as const;
const BREEDING_LOGBOOK_PLANT_METRIC_HISTORY_PATH =
  "/api/breeding-logbook/plants/{plant_key}/metrics/history" as const;

type HostedBreedingLogbookBootstrap =
  hostedComponents["schemas"]["BreedingLogbookBootstrapResponse"];
type HostedBreedingLogbookPlantList =
  hostedComponents["schemas"]["BreedingLogbookPlantListResponse"];
type HostedBreedingLogbookPlantDetail =
  hostedComponents["schemas"]["BreedingLogbookPlantDetailResponse"];
type HostedBreedingLogbookSeedLotList =
  hostedComponents["schemas"]["BreedingLogbookSeedLotListResponse"];
type HostedPlantMetricHistory =
  hostedComponents["schemas"]["PlantMetricHistoryResponse"];

const breedingLogbookQueryKeys = {
  bootstrap: ["breeding-logbook", "bootstrap"],
  plants: ["breeding-logbook", "plants"],
  seedLots: ["breeding-logbook", "seed-lots"],
  plantDetail: (plantKey: string) => [
    "breeding-logbook",
    "plants",
    plantKey || "first",
    "detail",
  ],
} as const;

export function invalidateBreedingLogbookReads(
  queryClient: QueryClient,
  plantKeys: readonly string[] = [],
): void {
  void queryClient.invalidateQueries({
    queryKey: breedingLogbookQueryKeys.bootstrap,
  });
  void queryClient.invalidateQueries({
    queryKey: breedingLogbookQueryKeys.seedLots,
  });
  void queryClient.invalidateQueries({
    queryKey: breedingLogbookQueryKeys.plants,
  });
  for (const plantKey of plantKeys) {
    void queryClient.invalidateQueries({
      queryKey: breedingLogbookQueryKeys.plantDetail(plantKey),
    });
  }
}

async function fetchBreedingLogbookBootstrap(): Promise<BreedingLogbookBootstrap> {
  const { data } = await hostedApi.GET("/api/breeding-logbook/bootstrap");
  return mapBootstrap(hostedData(data, "/api/breeding-logbook/bootstrap"));
}

async function fetchBreedingLogbookPlants(): Promise<PlantListResult> {
  const { data } = await hostedApi.GET("/api/breeding-logbook/plants", {
    params: { query: { include_culled: true, group_by: "stage" } },
  });
  return mapPlantList(hostedData(data, "/api/breeding-logbook/plants"));
}

async function fetchBreedingLogbookSeedLots(): Promise<SeedLotListResult> {
  const { data } = await hostedApi.GET("/api/breeding-logbook/seed-lots");
  return mapSeedLotList(hostedData(data, "/api/breeding-logbook/seed-lots"));
}

async function fetchBreedingLogbookPlantDetail(
  plantKey: string,
  queryClient: QueryClient,
): Promise<PlantDetail> {
  const resolvedPlantKey =
    plantKey ||
    (await queryClient.ensureQueryData(breedingLogbookPlantsOptions())).plants[0]?.key;
  if (!resolvedPlantKey) {
    throw new Error("Breeding Logbook has no plants to select");
  }
  const [detailResponse, historyResponse] = await Promise.all([
    hostedApi.GET(BREEDING_LOGBOOK_PLANT_DETAIL_PATH, {
      params: { path: { plant_key: resolvedPlantKey } },
    }),
    hostedApi.GET(BREEDING_LOGBOOK_PLANT_METRIC_HISTORY_PATH, {
      params: {
        path: { plant_key: resolvedPlantKey },
        query: { range: "24h" },
      },
    }),
  ]);
  return mapPlantDetail(
    hostedData(detailResponse.data, BREEDING_LOGBOOK_PLANT_DETAIL_PATH),
    hostedData(historyResponse.data, BREEDING_LOGBOOK_PLANT_METRIC_HISTORY_PATH),
  );
}

function breedingLogbookBootstrapOptions() {
  return queryOptions({
    queryKey: breedingLogbookQueryKeys.bootstrap,
    queryFn: fetchBreedingLogbookBootstrap,
    staleTime: Infinity,
  });
}

function breedingLogbookPlantsOptions() {
  return queryOptions({
    queryKey: breedingLogbookQueryKeys.plants,
    queryFn: fetchBreedingLogbookPlants,
    staleTime: Infinity,
  });
}

function breedingLogbookSeedLotsOptions() {
  return queryOptions({
    queryKey: breedingLogbookQueryKeys.seedLots,
    queryFn: fetchBreedingLogbookSeedLots,
    staleTime: Infinity,
  });
}

function breedingLogbookPlantDetailOptions(plantKey: string, queryClient: QueryClient) {
  return queryOptions({
    queryKey: breedingLogbookQueryKeys.plantDetail(plantKey),
    queryFn: () => fetchBreedingLogbookPlantDetail(plantKey, queryClient),
    staleTime: Infinity,
  });
}

export function useBreedingLogbookQueries(plantKey: string) {
  const queryClient = useQueryClient();
  return useSuspenseQueries({
    queries: [
      breedingLogbookBootstrapOptions(),
      breedingLogbookPlantsOptions(),
      breedingLogbookSeedLotsOptions(),
      breedingLogbookPlantDetailOptions(plantKey, queryClient),
    ],
    combine: ([bootstrap, plants, seedLots, detail]) => ({
      bootstrap: bootstrap.data,
      plants: plants.data,
      seedLots: seedLots.data,
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

export function mapBootstrap(
  response: HostedBreedingLogbookBootstrap,
): BreedingLogbookBootstrap {
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

export function mapPlantList(
  response: HostedBreedingLogbookPlantList,
): PlantListResult {
  return {
    activeCount: response.active_count,
    culledCount: response.culled_count,
    plants: response.plants.map(mapPlantRow),
  };
}

export function mapSeedLotList(
  response: HostedBreedingLogbookSeedLotList,
): SeedLotListResult {
  return {
    seedLots: response.seed_lots.map((seedLot) => ({
      id: seedLot.id,
      label: seedLot.label,
      prefix: seedLot.prefix,
      strain: seedLot.strain,
      cultivar: seedLot.cultivar,
      generation: seedLot.generation,
      source: seedLot.source,
      sourceLabel: seedLot.source_label,
      parentsLabel: seedLot.parents_label,
      sexTypeKey: seedLot.sex_type_key,
      seedCount: seedLot.seed_count,
    })),
  };
}

export function mapPlantDetail(
  detail: HostedBreedingLogbookPlantDetail,
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
    events: detail.events.map((event) => ({
      id: event.id,
      dateLabel: event.date_label,
      tag: event.tag,
      body: event.body,
      hasPhoto: event.has_photo,
    })),
  };
}

function mapPlantRow(
  plant: HostedBreedingLogbookPlantList["plants"][number],
): PlantRow {
  return {
    id: plant.id,
    key: plant.key,
    name: plant.name,
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
