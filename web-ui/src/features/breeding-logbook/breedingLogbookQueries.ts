import type { QueryClient } from "@tanstack/react-query";
import { queryOptions, useSuspenseQueries } from "@tanstack/react-query";
import {
  BREEDING_LOGBOOK_BOOTSTRAP,
  BREEDING_LOGBOOK_PLANTS,
  BREEDING_LOGBOOK_SEED_LOTS,
  BREEDING_LOGBOOK_SELECTED_PLANT_DETAIL,
} from "./breedingLogbook.mockData";
import type {
  BreedingLogbookBootstrap,
  LocationOption,
  PlantDetail,
  PlantJournalEvent,
  PlantListResult,
  PlantMetricHistory,
  PlantMetricSummary,
  PlantRow,
  PlantSexKey,
  SeedLotListResult,
  SeedLotSummary,
} from "./breedingLogbookTypes";

const breedingLogbookQueryKeys = {
  bootstrap: ["breeding-logbook", "bootstrap"],
  plants: ["breeding-logbook", "plants"],
  seedLots: ["breeding-logbook", "seed-lots"],
  plantDetail: (plantId: string) => ["breeding-logbook", "plants", plantId, "detail"],
} as const;

const MOCK_TODAY = "2026-06-17";
const MOCK_TODAY_LABEL = "Jun 17";
const mockCounters = {
  seedLot: 1,
  plantBatch: 1,
  cloneBatch: 1,
  event: 1,
};

async function fetchBreedingLogbookBootstrap(): Promise<BreedingLogbookBootstrap> {
  return BREEDING_LOGBOOK_BOOTSTRAP;
}

async function fetchBreedingLogbookPlants(): Promise<PlantListResult> {
  return BREEDING_LOGBOOK_PLANTS;
}

async function fetchBreedingLogbookSeedLots(): Promise<SeedLotListResult> {
  return BREEDING_LOGBOOK_SEED_LOTS;
}

async function fetchBreedingLogbookPlantDetail(plantId: string): Promise<PlantDetail> {
  const plant =
    BREEDING_LOGBOOK_PLANTS.plants.find((candidate) => candidate.id === plantId) ??
    requireFirstMockPlant();
  return buildMockPlantDetail(plant);
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

function breedingLogbookPlantDetailOptions(plantId: string) {
  return queryOptions({
    queryKey: breedingLogbookQueryKeys.plantDetail(plantId),
    queryFn: () => fetchBreedingLogbookPlantDetail(plantId),
    staleTime: Infinity,
  });
}

export function useBreedingLogbookQueries(plantId: string) {
  return useSuspenseQueries({
    queries: [
      breedingLogbookBootstrapOptions(),
      breedingLogbookPlantsOptions(),
      breedingLogbookSeedLotsOptions(),
      breedingLogbookPlantDetailOptions(plantId),
    ],
    combine: ([bootstrap, plants, seedLots, detail]) => ({
      bootstrap: bootstrap.data,
      plants: plants.data,
      seedLots: seedLots.data,
      detail: detail.data,
    }),
  });
}

export function applyMockBulkSex(
  queryClient: QueryClient,
  plantIds: ReadonlySet<string>,
  sexKey: PlantSexKey,
): void {
  if (plantIds.size === 0) return;
  const updatedPlants = updateMockPlants(queryClient, (plant) =>
    plantIds.has(plant.id) ? { ...plant, sexKey } : plant,
  );
  for (const plant of updatedPlants.filter((candidate) => plantIds.has(candidate.id))) {
    setMockDetailPlant(queryClient, plant);
  }
}

export function applyMockBulkMove(
  queryClient: QueryClient,
  plantIds: ReadonlySet<string>,
  location: LocationOption,
): void {
  if (plantIds.size === 0) return;
  const moveEvent = makeMockEvent(
    "stage",
    `Moved to ${location.displayName}; mock-local board/bulk move.`,
  );
  const updatedPlants = updateMockPlants(queryClient, (plant) => {
    if (!plantIds.has(plant.id)) return plant;
    return moveMockPlant(plant, location);
  });
  for (const plant of updatedPlants.filter((candidate) => plantIds.has(candidate.id))) {
    setMockDetailPlant(queryClient, plant, moveEvent);
  }
}

export function applyMockBulkCull(
  queryClient: QueryClient,
  plantIds: ReadonlySet<string>,
): void {
  if (plantIds.size === 0) return;
  const cullEvent = makeMockEvent("stage", "Marked culled in mock logbook.");
  const updatedPlants = updateMockPlants(queryClient, (plant) =>
    plantIds.has(plant.id)
      ? {
          ...plant,
          stageKey: "culled",
          stageDay: 0,
          culledOn: MOCK_TODAY,
          locationKey: "removed",
          locationLabel: "Removed",
          lastNote: "Culled 06/17 in mock logbook.",
        }
      : plant,
  );
  for (const plant of updatedPlants.filter((candidate) => plantIds.has(candidate.id))) {
    setMockDetailPlant(queryClient, plant, cullEvent);
  }
}

export function applyMockAddSeedLot(
  queryClient: QueryClient,
  seedLot: Omit<SeedLotSummary, "id">,
): SeedLotSummary {
  const created = {
    ...seedLot,
    id: nextMockId("seedLot"),
  };
  queryClient.setQueryData<SeedLotListResult>(
    breedingLogbookQueryKeys.seedLots,
    (current) => ({
      seedLots: [created, ...(current?.seedLots ?? [])],
    }),
  );
  return created;
}

export function applyMockSowPlants(
  queryClient: QueryClient,
  input: {
    seedLot: SeedLotSummary;
    count: number;
    location: LocationOption;
  },
): void {
  const batch = nextMockId("plantBatch");
  const newPlants = Array.from({ length: input.count }, (_, index): PlantRow => {
    const suffix = String(index + 1).padStart(2, "0");
    return {
      id: `${batch}-${suffix}`,
      key: `${input.seedLot.prefix}-${batch.toUpperCase()}-${suffix}`,
      name: `${input.seedLot.prefix}-${suffix}`,
      generation: input.seedLot.generation,
      parentsLabel: input.seedLot.parentsLabel,
      sexKey: "unknown",
      stageKey: input.location.stageKey,
      stageDay: 0,
      germinatedOn: MOCK_TODAY,
      vegStartedOn: input.location.stageKey === "veg" ? MOCK_TODAY : null,
      flowerStartedOn: input.location.stageKey === "flower" ? MOCK_TODAY : null,
      culledOn: null,
      locationKey: input.location.key,
      locationLabel: input.location.displayName,
      seedLotLabel: input.seedLot.label,
      lastNote: "Sown 06/17 in mock logbook.",
      telemetrySummary: "tent context",
    };
  });
  appendMockPlants(queryClient, newPlants);
  for (const plant of newPlants) {
    setMockDetailPlant(
      queryClient,
      plant,
      makeMockEvent("germ", `Sown from ${input.seedLot.label} in mock logbook.`),
    );
  }
}

export function applyMockTakeClones(
  queryClient: QueryClient,
  input: {
    mother: PlantRow;
    count: number;
    location: LocationOption;
    prefix: string;
  },
): void {
  const batch = nextMockId("cloneBatch");
  const newPlants = Array.from({ length: input.count }, (_, index): PlantRow => {
    const suffix = String(index + 1).padStart(2, "0");
    return {
      id: `${batch}-${suffix}`,
      key: `${input.prefix}-${batch.toUpperCase()}-${suffix}`,
      name: `${input.prefix}-${suffix}`,
      generation: input.mother.generation,
      parentsLabel: `clone of ${input.mother.name}`,
      sexKey: input.mother.sexKey,
      stageKey: input.location.stageKey,
      stageDay: 0,
      germinatedOn: MOCK_TODAY,
      vegStartedOn: MOCK_TODAY,
      flowerStartedOn: input.location.stageKey === "flower" ? MOCK_TODAY : null,
      culledOn: null,
      locationKey: input.location.key,
      locationLabel: input.location.displayName,
      seedLotLabel: "Clone preservation",
      lastNote: `Clone of ${input.mother.name}; cut 06/17.`,
      telemetrySummary: "clone context",
    };
  });
  appendMockPlants(queryClient, newPlants);
  for (const plant of newPlants) {
    setMockDetailPlant(
      queryClient,
      plant,
      makeMockEvent("note", `Clone cut from ${input.mother.name} in mock logbook.`),
    );
  }
}

export function applyMockLogNote(
  queryClient: QueryClient,
  plant: PlantRow,
  text: string,
): void {
  const noteText = text.trim();
  if (!noteText) return;
  setMockDetailPlant(queryClient, plant, makeMockEvent("note", noteText));
  updateMockPlants(queryClient, (candidate) =>
    candidate.id === plant.id ? { ...candidate, lastNote: noteText } : candidate,
  );
}

function updateMockPlants(
  queryClient: QueryClient,
  updatePlant: (plant: PlantRow) => PlantRow,
): readonly PlantRow[] {
  let nextPlants: readonly PlantRow[] = [];
  queryClient.setQueryData<PlantListResult>(
    breedingLogbookQueryKeys.plants,
    (current) => {
      const base = current ?? BREEDING_LOGBOOK_PLANTS;
      nextPlants = base.plants.map(updatePlant);
      return withMockCounts(nextPlants);
    },
  );
  return nextPlants;
}

function appendMockPlants(
  queryClient: QueryClient,
  newPlants: readonly PlantRow[],
): void {
  queryClient.setQueryData<PlantListResult>(
    breedingLogbookQueryKeys.plants,
    (current) => {
      const base = current ?? BREEDING_LOGBOOK_PLANTS;
      return withMockCounts([...base.plants, ...newPlants]);
    },
  );
}

function withMockCounts(plants: readonly PlantRow[]): PlantListResult {
  return {
    activeCount: plants.filter((plant) => plant.stageKey !== "culled").length,
    culledCount: plants.filter((plant) => plant.stageKey === "culled").length,
    plants,
  };
}

function moveMockPlant(plant: PlantRow, location: LocationOption): PlantRow {
  return {
    ...plant,
    stageKey: location.stageKey,
    stageDay: 0,
    vegStartedOn:
      location.stageKey === "veg" && plant.vegStartedOn === null
        ? MOCK_TODAY
        : plant.vegStartedOn,
    flowerStartedOn:
      location.stageKey === "flower" && plant.flowerStartedOn === null
        ? MOCK_TODAY
        : plant.flowerStartedOn,
    culledOn: null,
    locationKey: location.key,
    locationLabel: location.displayName,
    lastNote: `Moved to ${location.displayName} on 06/17.`,
  };
}

function setMockDetailPlant(
  queryClient: QueryClient,
  plant: PlantRow,
  event?: PlantJournalEvent,
): void {
  queryClient.setQueryData<PlantDetail>(
    breedingLogbookQueryKeys.plantDetail(plant.id),
    (current) => {
      const base = current ?? buildMockPlantDetail(plant);
      return {
        ...base,
        plant,
        events: event ? [event, ...base.events] : base.events,
      };
    },
  );
}

function buildMockPlantDetail(plant: PlantRow): PlantDetail {
  const fixture =
    plant.id === BREEDING_LOGBOOK_SELECTED_PLANT_DETAIL.plant.id
      ? BREEDING_LOGBOOK_SELECTED_PLANT_DETAIL
      : null;
  return {
    plant,
    lineage: fixture?.lineage ?? {
      parents: plant.parentsLabel,
      offspring: plant.parentsLabel.startsWith("clone of")
        ? "—"
        : "No offspring logged",
    },
    metrics: fixture?.metrics ?? defaultMockMetrics(plant),
    metricHistory: fixture?.metricHistory ?? defaultMockMetricHistory(plant),
    events: fixture?.events ?? [
      {
        id: nextMockId("event"),
        dateLabel: MOCK_TODAY_LABEL,
        tag: "germ",
        body: `Recorded ${plant.name} in mock logbook.`,
        hasPhoto: false,
      },
    ],
  };
}

function requireFirstMockPlant(): PlantRow {
  const plant = BREEDING_LOGBOOK_PLANTS.plants[0];
  if (plant === undefined) {
    throw new Error("Breeding Logbook mock plant fixture is empty");
  }
  return plant;
}

function defaultMockMetrics(plant: PlantRow): readonly PlantMetricSummary[] {
  return [
    {
      label: "Substrate moisture",
      value: plant.stageKey === "flower" ? "31%" : "38%",
      tone: "ok",
    },
    { label: "Substrate EC", value: "1.28", tone: "ok" },
    { label: "Air temp", value: "24.8C", tone: "ok" },
  ];
}

function defaultMockMetricHistory(plant: PlantRow): readonly PlantMetricHistory[] {
  const moisture =
    plant.stageKey === "flower" ? [30, 32, 31, 29, 30, 31] : [41, 39, 38, 40, 38, 39];
  return [
    {
      key: "moisture",
      label: "Substrate moisture",
      value: String(moisture.at(-1) ?? 0),
      unit: "%",
      tone: "ok",
      points: moisture,
    },
    {
      key: "ec",
      label: "Substrate EC",
      value: "1.28",
      unit: "mS",
      tone: "ok",
      points: [1.1, 1.18, 1.22, 1.26, 1.25, 1.28],
    },
    {
      key: "ph",
      label: "pH",
      value: "6.0",
      unit: "",
      tone: "ok",
      points: [6.2, 6.1, 6.0, 5.9, 6.1, 6.0],
    },
    {
      key: "temperature",
      label: "Air temp",
      value: "24.8",
      unit: "C",
      tone: "ok",
      points: [24.2, 24.4, 24.6, 24.7, 24.9, 24.8],
    },
  ];
}

function makeMockEvent(tag: PlantJournalEvent["tag"], body: string): PlantJournalEvent {
  return {
    id: nextMockId("event"),
    dateLabel: MOCK_TODAY_LABEL,
    tag,
    body,
    hasPhoto: false,
  };
}

function nextMockId(prefix: keyof typeof mockCounters): string {
  const value = mockCounters[prefix];
  mockCounters[prefix] += 1;
  return `mock-${prefix}-${String(value).padStart(3, "0")}`;
}
