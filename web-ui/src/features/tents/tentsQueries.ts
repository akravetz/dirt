import { queryOptions } from "@tanstack/react-query";
import { createHostedApiClient, type hostedComponents } from "@/api-client";

const hostedApi = createHostedApiClient();
const TENT_PLANT_METRIC_HISTORY_API_PATH =
  "/api/tents/{source_tent_id}/plants/metrics/history" as const;

export const TENTS_REFETCH_MS = 30_000;

type HostedTentPlantMetricHistory =
  hostedComponents["schemas"]["PlantMetricHistoryCollectionResponse"];
type TentPlantMetricHistoryRange = HostedTentPlantMetricHistory["range"];

export function tentPlantMetricHistoryQueryOptions(
  sourceTentId: number,
  range: TentPlantMetricHistoryRange,
) {
  return queryOptions({
    queryKey: ["cloud.plants.metrics.history", sourceTentId, range],
    queryFn: async () => {
      const { data } = await hostedApi.GET(TENT_PLANT_METRIC_HISTORY_API_PATH, {
        params: {
          path: { source_tent_id: sourceTentId },
          query: { range },
        },
      });
      if (data === undefined) {
        throw new Error(`${TENT_PLANT_METRIC_HISTORY_API_PATH} returned no data`);
      }
      return data;
    },
    refetchInterval: TENTS_REFETCH_MS,
  });
}
