import type { SeedLotSexTypeKey, SeedLotSummary } from "@/shared/seedLots";

export type {
  SeedLotListResult,
  SeedLotSexTypeKey,
  SeedLotSource,
  SeedLotSummary,
} from "@/shared/seedLots";

export type LookupRow<TKey extends string> = {
  key: TKey;
  displayName: string;
  displayOrder: number;
};

export type SeedsBootstrap = {
  today: string;
  todayLabel: string;
  seedLotSexTypes: readonly LookupRow<SeedLotSexTypeKey>[];
};

export type SeedParentPlant = {
  id: string;
  key: string;
  name: string;
  sexKey: "unknown" | "male" | "female" | "herm" | "reversed";
  stageKey: "germinating" | "veg" | "flower" | "breeding" | "harvested" | "culled";
};

export type SeedLotLine = {
  sourceLineId: number;
  prefix: string;
  strain: string;
  cultivar: string;
  generation: string;
  sourceName: string | null;
  description: string | null;
};

export type SeedLotCrossContext = {
  sourceCrossEventId: number;
  parentsLabel: string;
  seedParentSourcePlantId: number;
  seedParentKey: string | null;
  seedParentName: string | null;
  seedParentLabel: string;
  pollenParentSourcePlantId: number;
  pollenParentKey: string | null;
  pollenParentName: string | null;
  pollenParentLabel: string;
  pollenParentIsReversed: boolean | null;
  pollinatedAt: string;
  notes: string | null;
};

export type SeedLotDetail = SeedLotSummary & {
  sourceSeedLotId: number;
  sourceLineId: number;
  isPurchased: boolean;
  vendorName: string | null;
  acquiredAt: string | null;
  notes: string | null;
  createdPlantCount: number;
  producedByCrossEventSourceId: number | null;
  line: SeedLotLine | null;
  cross: SeedLotCrossContext | null;
};
