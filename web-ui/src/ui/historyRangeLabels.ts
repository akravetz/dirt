import type { SparklineRange } from "@/ui/RangeSwitch";

export function formatEmptyHistoryLabel(range: SparklineRange): string {
  return `No data in the last ${range}`;
}
