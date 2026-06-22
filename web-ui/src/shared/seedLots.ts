import type { QueryClient } from "@tanstack/react-query";

export type SeedLotSource = "cross" | "purchased";
export type SeedLotSexTypeKey = "unknown" | "feminized" | "regular";

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

export type SeedLotListResult = {
  seedLots: readonly SeedLotSummary[];
};

export const seedLotQueryKeys = {
  seedLots: ["breeding-logbook", "seed-lots"] as const,
  seedLotDetail: (seedLotId: string) =>
    ["breeding-logbook", "seed-lots", seedLotId, "detail"] as const,
};

export function invalidateSeedLotReads(
  queryClient: QueryClient,
  seedLotIds: readonly string[] = [],
): void {
  void queryClient.invalidateQueries({
    queryKey: seedLotQueryKeys.seedLots,
  });
  for (const seedLotId of seedLotIds) {
    void queryClient.invalidateQueries({
      queryKey: seedLotQueryKeys.seedLotDetail(seedLotId),
    });
  }
}
