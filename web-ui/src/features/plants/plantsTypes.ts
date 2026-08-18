import type { SeedLotSexTypeKey } from "@/shared/seedLots";

export type PlantListLayout = "table" | "board";
export type PlantGroupBy = "stage" | "parents";
export type BulkPanel = "sex" | "sex-test" | "dates" | "move" | "cull" | null;
export type PlantSexKey = "unknown" | "male" | "female" | "herm" | "reversed";
export type PlantSexTestResultSexKey = Extract<PlantSexKey, "female" | "male">;
export type PlantStageKey =
  | "germinating"
  | "veg"
  | "flower"
  | "breeding"
  | "harvested"
  | "culled";

export type LookupRow<TKey extends string> = {
  key: TKey;
  displayName: string;
  displayOrder: number;
};

export type LocationOption = {
  sourceTentId: number;
  displayName: string;
  role: string | null;
};

export type PlantSexTest = {
  id: string;
  sourceSexTestId: number;
  sourcePlantId: number;
  vendorName: string;
  assayName: string | null;
  vendorTestCode: string;
  sampleCollectedAt: string;
  sampleSentAt: string | null;
  resultReceivedAt: string | null;
  resultSexKey: PlantSexTestResultSexKey | null;
  isInconclusive: boolean;
  notes: string | null;
};

export type PlantsBootstrap = {
  today: string;
  todayLabel: string;
  plantSexes: readonly LookupRow<PlantSexKey>[];
  seedLotSexTypes: readonly LookupRow<SeedLotSexTypeKey>[];
  stages: readonly LookupRow<PlantStageKey>[];
  locations: readonly LocationOption[];
};

export type PlantRow = {
  id: string;
  key: string;
  name: string;
  strain: string;
  generation: string;
  parentsLabel: string;
  sexKey: PlantSexKey;
  stageKey: PlantStageKey;
  stageDay: number;
  isClone: boolean;
  germinatedAt: string | null;
  germinatedOn: string | null;
  takenAt: string | null;
  takenOn: string | null;
  rootedAt: string | null;
  rootedOn: string | null;
  vegStartedAt: string | null;
  vegStartedOn: string | null;
  flowerStartedAt: string | null;
  flowerStartedOn: string | null;
  culledAt: string | null;
  culledOn: string | null;
  culledReason: string | null;
  harvestedAt: string | null;
  harvestedOn: string | null;
  selectedForBreedingAt: string | null;
  selectedForBreedingOn: string | null;
  selectedForBreedingReason: string | null;
  currentTentId: number;
  currentTentName: string;
  gridPosition: string | null;
  seedLotLabel: string;
  lastNote: string;
  telemetrySummary: string;
  sexTests: readonly PlantSexTest[];
};

export type PlantTelemetryReading = {
  receivedAt: string;
  value: number;
};

export type PlantTelemetryStream = {
  accent: string;
  capabilityId: string;
  deviceId: string;
  displayName: string;
  displayUnit: string;
  historyEnabled: boolean;
  key: string;
  latestReading: PlantTelemetryReading | null;
  metric: string;
  valuePrecision: number;
  yMax: number | null;
  yMin: number | null;
};

export type PlantWikiContent = {
  bodyMarkdown: string;
  sourceUpdatedAt: string;
  title: string;
};

export type PlantJournalEvent = {
  id: string;
  dateLabel: string;
  tag: "cross" | "note" | "stage" | "sex" | "germ";
  body: string;
  hasPhoto: boolean;
};

export type PlantDetail = {
  plant: PlantRow;
  lineage: {
    parents: string;
    offspring: string;
  };
  telemetry: readonly PlantTelemetryStream[];
  wikiContent: PlantWikiContent | null;
  events: readonly PlantJournalEvent[];
};

export type PlantListResult = {
  activeCount: number;
  culledCount: number;
  plants: readonly PlantRow[];
};
