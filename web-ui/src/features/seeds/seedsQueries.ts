import {
  queryOptions,
  useSuspenseQueries,
  useSuspenseQuery,
} from "@tanstack/react-query";
import { createHostedApiClient, type hostedComponents } from "@/api-client";
import { seedLotQueryKeys } from "@/shared/seedLots";
import type {
  SeedLotDetail,
  SeedLotListResult,
  SeedLotSexTypeKey,
  SeedParentPlant,
  SeedsBootstrap,
} from "./seedsTypes";

const hostedApi = createHostedApiClient();
const SEED_LOT_DETAIL_API_PATH =
  "/api/breeding-logbook/seed-lots/{seed_lot_id}" as const;

type HostedBootstrap = hostedComponents["schemas"]["BreedingLogbookBootstrapResponse"];
type HostedPlantList = hostedComponents["schemas"]["BreedingLogbookPlantListResponse"];
type HostedSeedLotList =
  hostedComponents["schemas"]["BreedingLogbookSeedLotListResponse"];
type HostedSeedLotDetail =
  hostedComponents["schemas"]["BreedingLogbookSeedLotDetailResponse"];

const seedsQueryKeys = {
  bootstrap: ["seeds", "bootstrap"] as const,
  seedLots: seedLotQueryKeys.seedLots,
  seedParentPlants: ["seeds", "seed-parent-plants"] as const,
  seedLotDetail: seedLotQueryKeys.seedLotDetail,
};

export { invalidateSeedLotReads } from "@/shared/seedLots";

async function fetchSeedsBootstrap(): Promise<SeedsBootstrap> {
  const { data } = await hostedApi.GET("/api/breeding-logbook/bootstrap");
  return mapSeedsBootstrap(hostedData(data, "/api/breeding-logbook/bootstrap"));
}

async function fetchSeedLots(): Promise<SeedLotListResult> {
  const { data } = await hostedApi.GET("/api/breeding-logbook/seed-lots");
  return mapSeedLotList(hostedData(data, "/api/breeding-logbook/seed-lots"));
}

async function fetchSeedParentPlants(): Promise<readonly SeedParentPlant[]> {
  const { data } = await hostedApi.GET("/api/breeding-logbook/plants", {
    params: { query: { include_culled: true, group_by: "stage" } },
  });
  return mapSeedParentPlants(hostedData(data, "/api/breeding-logbook/plants"));
}

async function fetchSeedLotDetail(seedLotId: string): Promise<SeedLotDetail> {
  const { data } = await hostedApi.GET(SEED_LOT_DETAIL_API_PATH, {
    params: { path: { seed_lot_id: seedLotId } },
  });
  return mapSeedLotDetail(hostedData(data, SEED_LOT_DETAIL_API_PATH));
}

function seedsBootstrapOptions() {
  return queryOptions({
    queryKey: seedsQueryKeys.bootstrap,
    queryFn: fetchSeedsBootstrap,
    staleTime: Infinity,
  });
}

function seedLotListOptions() {
  return queryOptions({
    queryKey: seedsQueryKeys.seedLots,
    queryFn: fetchSeedLots,
    staleTime: Infinity,
  });
}

function seedParentPlantsOptions() {
  return queryOptions({
    queryKey: seedsQueryKeys.seedParentPlants,
    queryFn: fetchSeedParentPlants,
    staleTime: Infinity,
  });
}

function seedLotDetailOptions(seedLotId: string) {
  return queryOptions({
    queryKey: seedsQueryKeys.seedLotDetail(seedLotId),
    queryFn: () => fetchSeedLotDetail(seedLotId),
    staleTime: Infinity,
  });
}

export function useSeedLotListPageQueries() {
  return useSuspenseQueries({
    queries: [seedsBootstrapOptions(), seedLotListOptions()],
    combine: ([bootstrap, seedLots]) => ({
      bootstrap: bootstrap.data,
      seedLots: seedLots.data,
    }),
  });
}

export function useSeedLotListQuery(): SeedLotListResult {
  return useSuspenseQuery(seedLotListOptions()).data;
}

export function useNewSeedLotPageQueries() {
  return useSuspenseQueries({
    queries: [seedsBootstrapOptions(), seedLotListOptions(), seedParentPlantsOptions()],
    combine: ([bootstrap, seedLots, seedParentPlants]) => ({
      bootstrap: bootstrap.data,
      seedLots: seedLots.data,
      seedParentPlants: seedParentPlants.data,
    }),
  });
}

export function useSeedLotDetailPageQueries(seedLotId: string) {
  return useSuspenseQueries({
    queries: [seedsBootstrapOptions(), seedLotDetailOptions(seedLotId)],
    combine: ([bootstrap, detail]) => ({
      bootstrap: bootstrap.data,
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

export function mapSeedsBootstrap(response: HostedBootstrap): SeedsBootstrap {
  return {
    today: response.today,
    todayLabel: response.today_label,
    seedLotSexTypes: response.seed_lot_sex_types.map((row) => ({
      key: toSeedLotSexTypeKey(row.key),
      displayName: row.display_name,
      displayOrder: row.display_order,
    })),
  };
}

export function mapSeedLotList(response: HostedSeedLotList): SeedLotListResult {
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

export function mapSeedLotDetail(response: HostedSeedLotDetail): SeedLotDetail {
  return {
    id: response.id,
    label: response.label,
    prefix: response.prefix,
    strain: response.strain,
    cultivar: response.cultivar,
    generation: response.generation,
    source: response.source,
    sourceLabel: response.source_label,
    parentsLabel: response.parents_label,
    sexTypeKey: response.sex_type_key,
    seedCount: response.seed_count,
    sourceSeedLotId: response.source_seed_lot_id,
    sourceLineId: response.source_line_id,
    isPurchased: response.is_purchased,
    vendorName: response.vendor_name,
    acquiredAt: response.acquired_at,
    notes: response.notes,
    createdPlantCount: response.created_plant_count,
    producedByCrossEventSourceId: response.produced_by_cross_event_source_id,
    line:
      response.line === null
        ? null
        : {
            sourceLineId: response.line.source_line_id,
            prefix: response.line.prefix,
            strain: response.line.strain,
            cultivar: response.line.cultivar,
            generation: response.line.generation,
            sourceName: response.line.source_name,
            description: response.line.description,
          },
    cross:
      response.cross === null
        ? null
        : {
            sourceCrossEventId: response.cross.source_cross_event_id,
            parentsLabel: response.cross.parents_label,
            seedParentSourcePlantId: response.cross.seed_parent_source_plant_id,
            seedParentKey: response.cross.seed_parent_key,
            seedParentName: response.cross.seed_parent_name,
            seedParentLabel: response.cross.seed_parent_label,
            pollenParentSourcePlantId: response.cross.pollen_parent_source_plant_id,
            pollenParentKey: response.cross.pollen_parent_key,
            pollenParentName: response.cross.pollen_parent_name,
            pollenParentLabel: response.cross.pollen_parent_label,
            pollenParentIsReversed: response.cross.pollen_parent_is_reversed,
            pollinatedAt: response.cross.pollinated_at,
            notes: response.cross.notes,
          },
  };
}

export function mapSeedParentPlants(
  response: HostedPlantList,
): readonly SeedParentPlant[] {
  return response.plants.map((plant) => ({
    id: plant.id,
    key: plant.key,
    name: plant.name,
    sexKey: plant.sex_key,
    stageKey: plant.stage_key,
  }));
}

function toSeedLotSexTypeKey(key: string): SeedLotSexTypeKey {
  if (key === "unknown" || key === "feminized" || key === "regular") return key;
  return "unknown";
}
