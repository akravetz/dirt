export type PlantListLayout = "table" | "board";
export type PlantGroupBy = "stage" | "parents";
export type BulkPanel = "sex" | "dates" | "move" | "cull" | null;
export type PlantSexKey = "unknown" | "male" | "female" | "herm" | "reversed";
export type PlantStageKey =
  | "germinating"
  | "veg"
  | "flower"
  | "breeding"
  | "harvested"
  | "culled";
export type SeedLotSource = "cross" | "purchased";
export type SeedLotSexTypeKey = "unknown" | "feminized" | "regular";

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

export type PlantsBootstrap = {
  today: string;
  todayLabel: string;
  plantSexes: readonly LookupRow<PlantSexKey>[];
  seedLotSexTypes: readonly LookupRow<SeedLotSexTypeKey>[];
  stages: readonly LookupRow<PlantStageKey>[];
  locations: readonly LocationOption[];
};

export type SeedLotSummary = {
  id: string;
  label: string;
  prefix: string;
  strain: string;
  cultivar: string;
  generation: string;
  source: SeedLotSource;
  sourceLabel: string;
  parentsLabel: string;
  sexTypeKey: SeedLotSexTypeKey;
  seedCount: number | null;
};

export type PlantRow = {
  id: string;
  key: string;
  name: string;
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
  culledOn: string | null;
  currentTentId: number;
  currentTentName: string;
  gridPosition: string | null;
  seedLotLabel: string;
  lastNote: string;
  telemetrySummary: string;
};

export type PlantMetricSummary = {
  label: string;
  value: string;
  tone: "ok" | "warn";
};

export type PlantMetricHistory = {
  key: "moisture" | "ec" | "ph" | "temperature";
  label: string;
  value: string;
  unit: string;
  tone: "ok" | "warn";
  points: readonly number[];
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
  metrics: readonly PlantMetricSummary[];
  metricHistory: readonly PlantMetricHistory[];
  telemetry: readonly PlantTelemetryStream[];
  wikiContent: PlantWikiContent | null;
  events: readonly PlantJournalEvent[];
};

export type PlantListResult = {
  activeCount: number;
  culledCount: number;
  plants: readonly PlantRow[];
};

export type SeedLotListResult = {
  seedLots: readonly SeedLotSummary[];
};
