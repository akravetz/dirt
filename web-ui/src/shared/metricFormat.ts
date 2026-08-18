export function formatMetricValue(value: number, precision: number): string {
  const safePrecision =
    Number.isInteger(precision) && precision >= 0 ? Math.min(precision, 6) : 1;
  return value.toFixed(safePrecision);
}

export function formatMetricDisplayValue(
  value: number,
  precision: number,
  unit: string,
): string {
  const formatted = formatMetricValue(value, precision);
  return unit === "raw" ? `${formatted} raw` : `${formatted}${unit}`;
}
