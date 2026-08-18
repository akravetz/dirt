import {
  type QueryClient,
  queryOptions,
  useQuery,
  useQueryClient,
  useSuspenseQueries,
} from "@tanstack/react-query";
import { createHostedApiClient, type hostedComponents } from "@/api-client";
import { invalidateSeedLotReads, type SeedLotSexTypeKey } from "@/shared/seedLots";
import type {
  PlantDetail,
  PlantListResult,
  PlantRow,
  PlantSexKey,
  PlantSexTest,
  PlantStageKey,
  PlantsBootstrap,
  PlantTelemetryStream,
} from "./plantsTypes";

const hostedApi = createHostedApiClient();
const PLANT_DETAIL_API_PATH = "/api/breeding-logbook/plants/{plant_key}" as const;
const PLANT_METRIC_HISTORY_API_PATH =
  "/api/breeding-logbook/plants/{plant_key}/metrics/history" as const;
const PLANT_HISTORY_REFETCH_MS = 30_000;

type HostedPlantsBootstrap =
  hostedComponents["schemas"]["BreedingLogbookBootstrapResponse"];
type HostedPlantsPlantList =
  hostedComponents["schemas"]["BreedingLogbookPlantListResponse"];
type HostedPlantsPlantDetail =
  hostedComponents["schemas"]["BreedingLogbookPlantDetailResponse"];
type HostedPlantMetricHistory =
  hostedComponents["schemas"]["PlantMetricHistoryResponse"];
type PlantMetricHistoryRange = HostedPlantMetricHistory["range"];
export type PlantMetricHistoryBucket = HostedPlantMetricHistory["bucket"];
export type PlantMetricHistoryStream = HostedPlantMetricHistory["streams"][number];
type HostedPlantSexTest = hostedComponents["schemas"]["BreedingLogbookSexTestResponse"];

const plantsQueryKeys = {
  bootstrap: ["plants", "bootstrap"],
  plants: ["plants", "list"],
  plantDetail: (plantKey: string) => ["plants", plantKey || "first", "detail"],
  plantHistory: (plantKey: string, range: PlantMetricHistoryRange) => [
    "plants",
    plantKey,
    "metrics",
    range,
  ],
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
  const { data } = await hostedApi.GET(PLANT_DETAIL_API_PATH, {
    params: { path: { plant_key: resolvedPlantKey } },
  });
  return mapPlantDetail(hostedData(data, PLANT_DETAIL_API_PATH));
}

async function fetchPlantMetricHistory(
  plantKey: string,
  range: PlantMetricHistoryRange,
): Promise<HostedPlantMetricHistory> {
  const { data } = await hostedApi.GET(PLANT_METRIC_HISTORY_API_PATH, {
    params: {
      path: { plant_key: plantKey },
      query: { range },
    },
  });
  return hostedData(data, PLANT_METRIC_HISTORY_API_PATH);
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

export function plantMetricHistoryQueryOptions(
  plantKey: string,
  range: PlantMetricHistoryRange,
) {
  return queryOptions({
    queryKey: plantsQueryKeys.plantHistory(plantKey, range),
    queryFn: () => fetchPlantMetricHistory(plantKey, range),
    refetchInterval: PLANT_HISTORY_REFETCH_MS,
  });
}

export function usePlantsQueries(
  plantKey: string,
  historyRange: PlantMetricHistoryRange,
) {
  const queryClient = useQueryClient();
  const metricHistoryQuery = useQuery({
    ...plantMetricHistoryQueryOptions(plantKey || "first", historyRange),
    enabled: plantKey.length > 0,
  });
  const logbook = useSuspenseQueries({
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
  return {
    ...logbook,
    metricHistory: metricHistoryQuery.data,
    metricHistoryError: metricHistoryQuery.isError,
    metricHistoryLoading: metricHistoryQuery.isLoading,
  };
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

export function mapPlantDetail(detail: HostedPlantsPlantDetail): PlantDetail {
  return {
    plant: mapPlantRow(detail.plant),
    lineage: {
      parents: detail.lineage.parents,
      offspring: detail.lineage.offspring,
    },
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
    capabilityId: stream.capability_id,
    deviceId: stream.device_id,
    latestReading:
      stream.latest_reading === null
        ? null
        : {
            value: stream.latest_reading.value,
          },
    metric: stream.metric,
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
    culledAt: plant.culled_at ?? null,
    culledOn: plant.culled_on,
    culledReason: plant.culled_reason,
    harvestedAt: plant.harvested_at ?? null,
    harvestedOn: plant.harvested_on,
    selectedForBreedingAt: plant.selected_for_breeding_at ?? null,
    selectedForBreedingOn: plant.selected_for_breeding_on,
    selectedForBreedingReason: plant.selected_for_breeding_reason,
    currentTentId: plant.current_tent_id,
    currentTentName: plant.current_tent_name,
    gridPosition: plant.grid_position,
    seedLotLabel: plant.seed_lot_label,
    lastNote: plant.last_note,
    telemetrySummary: plant.telemetry_summary,
    sexTests: plant.sex_tests.map(mapPlantSexTest),
  };
}

function mapPlantSexTest(sexTest: HostedPlantSexTest): PlantSexTest {
  return {
    id: sexTest.id,
    sourceSexTestId: sexTest.source_sex_test_id,
    sourcePlantId: sexTest.source_plant_id,
    vendorName: sexTest.vendor_name,
    assayName: sexTest.assay_name,
    vendorTestCode: sexTest.vendor_test_code,
    sampleCollectedAt: sexTest.sample_collected_at,
    sampleSentAt: sexTest.sample_sent_at,
    resultReceivedAt: sexTest.result_received_at,
    resultSexKey: sexTest.result_sex_key,
    isInconclusive: sexTest.is_inconclusive,
    notes: sexTest.notes,
  };
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
