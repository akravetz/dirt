import type { SparklineRange } from "@/ui/RangeSwitch";

export function formatEmptyHistoryLabel(range: SparklineRange): string {
  switch (range) {
    case "1h":
      return "No 5-minute data in the last hour";
    case "24h":
      return "No hourly data in the last 24 hours";
    case "7d":
      return "No 4-hour data in the last 7 days";
    case "30d":
      return "No 4-hour data in the last 30 days";
    case "90d":
      return "No daily data in the last 90 days";
  }
}
