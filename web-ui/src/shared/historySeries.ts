export type HistoryPoint = {
  ts: string;
  value: number | null;
};

export type HistoryBucket = "5m" | "1h" | "4h" | "1d";

export const PLANT_SERIES_COLORS = [
  "plant-a",
  "plant-b",
  "plant-c",
  "plant-d",
] as const;

export type PlantSeriesColor = (typeof PLANT_SERIES_COLORS)[number];

export function historyTimestampAxis(
  pointGroups: readonly (readonly HistoryPoint[])[],
  bucket?: HistoryBucket,
): string[] {
  const timestamps = new Set<string>();
  for (const points of pointGroups) {
    for (const point of points) timestamps.add(point.ts);
  }
  const sorted = [...timestamps].sort(compareTimestamps);
  if (bucket === undefined || sorted.length < 2) return sorted;

  const bucketMilliseconds = BUCKET_MILLISECONDS[bucket];
  const timestampsByTime = new Map(
    sorted.flatMap((timestamp) => {
      const time = Date.parse(timestamp);
      return Number.isFinite(time) ? [[time, timestamp] as const] : [];
    }),
  );
  const start = Date.parse(sorted[0] ?? "");
  const end = Date.parse(sorted.at(-1) ?? "");
  if (!Number.isFinite(start) || !Number.isFinite(end)) return sorted;

  const completeAxis: string[] = [];
  for (let time = start; time <= end; time += bucketMilliseconds) {
    completeAxis.push(timestampsByTime.get(time) ?? new Date(time).toISOString());
  }
  return completeAxis;
}

export function alignHistoryPoints(
  points: readonly HistoryPoint[],
  axis: readonly string[],
): HistoryPoint[] {
  const valuesByTimestamp = new Map(points.map((point) => [point.ts, point.value]));
  const valuesByTime = new Map(
    points.flatMap((point) => {
      const time = Date.parse(point.ts);
      return Number.isFinite(time) ? [[time, point.value] as const] : [];
    }),
  );
  return axis.map((ts) => ({
    ts,
    value: valuesByTimestamp.get(ts) ?? valuesByTime.get(Date.parse(ts)) ?? null,
  }));
}

const BUCKET_MILLISECONDS = {
  "5m": 5 * 60 * 1_000,
  "1h": 60 * 60 * 1_000,
  "4h": 4 * 60 * 60 * 1_000,
  "1d": 24 * 60 * 60 * 1_000,
} satisfies Record<HistoryBucket, number>;

function compareTimestamps(left: string, right: string): number {
  const leftTime = Date.parse(left);
  const rightTime = Date.parse(right);
  if (Number.isFinite(leftTime) && Number.isFinite(rightTime)) {
    return leftTime - rightTime;
  }
  return left.localeCompare(right);
}
