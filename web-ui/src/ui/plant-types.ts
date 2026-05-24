// Shared types + sticker-palette lookups for the plants UI layer.
// Kept local to ui/ because the `boundaries` lint rule forbids
// ui/ → api-client/ (eslint.config.ts). StickerColor mirrors
// contracts/webapp-v1.yaml #/components/schemas/PlantStickerColor.
// Drift surfaces in route typechecks against the real api-client types,
// so duplication here is a bounded cost.

export type PlantId = string;
export type StickerColor = "yellow" | "orange" | "pink" | "brown" | "blue";

// Sticker → Tailwind theme-token class lookups. Named tokens keep TS-15
// happy (no arbitrary hex values); see src/styles.css @theme for the
// palette. Exported so PlantCard + PlantDetail share one source of truth.
export const STICKER_BG = {
  yellow: "bg-sticker-yellow",
  orange: "bg-sticker-orange",
  pink: "bg-sticker-pink",
  brown: "bg-sensor-moisture",
  blue: "bg-sticker-blue",
} satisfies Record<StickerColor, string>;
const STICKER_FILL = {
  yellow: "fill-sticker-yellow",
  orange: "fill-sticker-orange",
  pink: "fill-sticker-pink",
  brown: "fill-sensor-moisture",
  blue: "fill-sticker-blue",
} satisfies Record<StickerColor, string>;
const STICKER_STROKE = {
  yellow: "stroke-sticker-yellow",
  orange: "stroke-sticker-orange",
  pink: "stroke-sticker-pink",
  brown: "stroke-sensor-moisture",
  blue: "stroke-sticker-blue",
} satisfies Record<StickerColor, string>;

export function isStickerColor(
  input: string | null | undefined,
): input is StickerColor {
  return (
    input === "yellow" ||
    input === "orange" ||
    input === "pink" ||
    input === "brown" ||
    input === "blue"
  );
}

export function stickerBgClass(stickerColor: StickerColor | null | undefined): string {
  return stickerColor === null || stickerColor === undefined
    ? "bg-paper"
    : STICKER_BG[stickerColor];
}

export function stickerFillClass(
  stickerColor: StickerColor | null | undefined,
): string {
  return stickerColor === null || stickerColor === undefined
    ? "fill-ink-3"
    : STICKER_FILL[stickerColor];
}

export function stickerStrokeClass(
  stickerColor: StickerColor | null | undefined,
): string {
  return stickerColor === null || stickerColor === undefined
    ? "stroke-ink-3"
    : STICKER_STROKE[stickerColor];
}
