export function formatMetricValue(value: number, precision: number): string {
  const safePrecision =
    Number.isInteger(precision) && precision >= 0 ? Math.min(precision, 6) : 1;
  return value.toFixed(safePrecision);
}
